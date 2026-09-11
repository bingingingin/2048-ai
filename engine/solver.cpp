// Expectimax and row heuristic adapted from nneonneo/2048-ai (MIT).
// See THIRD_PARTY_NOTICES.md. Board representation and search implementation
// below support rank 16 (65536); the upstream 4-bit representation does not.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <limits>
#include <mutex>
#include <vector>

#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif

namespace {
constexpr uint32_t MASK = (1u << 20) - 1;
constexpr double LOSS = -1e12;
constexpr double WIN = 1e12;
struct Board {
    uint32_t r[4]{};
    bool operator==(const Board& b) const {
        return r[0]==b.r[0] && r[1]==b.r[1] && r[2]==b.r[2] && r[3]==b.r[3];
    }
    unsigned at(int i) const { return (r[i/4] >> ((i%4)*5)) & 31; }
    void set(int i, unsigned v) { r[i/4] = (r[i/4] & ~(31u << ((i%4)*5))) | (v << ((i%4)*5)); }
};
std::vector<uint32_t> lefts(1<<20), rights(1<<20);
std::vector<double> heuristics(1<<20);
std::once_flag initialized;

uint32_t reverse(uint32_t r) {
    return ((r&31)<<15) | ((r&992)<<5) | ((r>>5)&992) | ((r>>15)&31);
}
void init() {
    double p4[32], p35[32];
    for (int i=0;i<32;i++) { p4[i]=std::pow(i,4); p35[i]=std::pow(i,3.5); }
    for (uint32_t row=0;row<=MASK;row++) {
        unsigned a[4], compact[4]{}, out[4]{};
        double sum=0, inc=0, dec=0;
        int empty=0, merges=0, previous=0, counter=0, n=0;
        for(int i=0;i<4;i++) {
            a[i]=(row>>(5*i))&31;
            sum+=p35[a[i]];
            if(!a[i]) { empty++; continue; }
            compact[n++]=a[i];
            if(previous==int(a[i])) counter++;
            else if(counter) { merges+=1+counter; counter=0; }
            previous=a[i];
        }
        if(counter) merges+=1+counter;
        for(int i=1;i<4;i++) {
            double d=p4[a[i-1]]-p4[a[i]];
            if(d>0) dec+=d; else inc-=d;
        }
        // Signed search scores: large ranks may make this negative. A legal
        // move must never be mistaken for game over because of its score.
        heuristics[row]=200000+270*empty+700*merges-47*std::min(inc,dec)-11*sum;
        int j=0;
        for(int i=0;i<n;i++) {
            if(i+1<n && compact[i]==compact[i+1] && compact[i]<31) {
                out[j++]=compact[i]+1; i++;
            } else out[j++]=compact[i];
        }
        uint32_t result=out[0]|(out[1]<<5)|(out[2]<<10)|(out[3]<<15);
        lefts[row]=result;
        rights[reverse(row)]=reverse(result);
    }
}
Board transpose(const Board& b) {
    Board t;
    for(int i=0;i<4;i++)
        t.r[i]=((b.r[0]>>(i*5))&31) | (((b.r[1]>>(i*5))&31)<<5)
             | (((b.r[2]>>(i*5))&31)<<10) | (((b.r[3]>>(i*5))&31)<<15);
    return t;
}
Board move(const Board& b, int d) {
    Board t = d<2 ? transpose(b) : b;
    const auto& table=(d==0 || d==2) ? lefts : rights;
    for(auto& r:t.r) r=table[r];
    return d<2 ? transpose(t) : t;
}
double heuristic(const Board& b) {
    Board t=transpose(b);
    double score=0;
    for(int i=0;i<4;i++) score+=heuristics[b.r[i]]+heuristics[t.r[i]];
    return score;
}
uint64_t mix(uint64_t x) {
    x^=x>>30; x*=0xbf58476d1ce4e5b9ULL; x^=x>>27;
    x*=0x94d049bb133111ebULL; return x^(x>>31);
}
struct Entry {
    Board board;
    double value=0;
    uint32_t generation=0;
    uint16_t depth=0;
    // Probability also depends on empty counts along the path. Use exact
    // double bits in the key, never reuse a differently pruned search.
    uint64_t probability=0;
};
struct Timeout {};
struct Search {
    std::vector<Entry> cache;
    uint32_t generation=0;
    uint64_t nodes=0, hits=0;
    double cutoff=0.0001;
    double terminalLoss=0;
    int targetRank=16;
    bool checkGoal=false;
    std::chrono::steady_clock::time_point deadline;
    bool timed=true;
    Search():cache(1<<18) {}
    void tick() {
        if((++nodes & 1023)==0 && timed && std::chrono::steady_clock::now()>=deadline) throw Timeout{};
    }
    double chance(const Board& b, int depth, double probability) {
        tick();
        if(checkGoal) {
            for(int i=0;i<16;i++) if(b.at(i)>=unsigned(targetRank)) return WIN;
        }
        if(depth<=0 || probability<cutoff) return heuristic(b);
        uint64_t bits;
        static_assert(sizeof(bits)==sizeof(probability), "double size");
        __builtin_memcpy(&bits,&probability,sizeof(bits));
        uint64_t h=mix(uint64_t(b.r[0]) | (uint64_t(b.r[1])<<20))
                  ^mix(uint64_t(b.r[2]) | (uint64_t(b.r[3])<<20)) ^mix(bits+depth);
        Entry& e=cache[h&(cache.size()-1)];
        if(e.generation==generation && e.depth==depth && e.probability==bits && e.board==b) {
            hits++; return e.value;
        }
        int indices[16], count=0;
        for(int i=0;i<16;i++) if(!b.at(i)) indices[count++]=i;
        if(!count) return player(b,depth-1,probability);
        double result=0;
        for(int k=0;k<count;k++) {
            Board child=b;
            child.set(indices[k],1);
            result+=0.9*player(child,depth-1,probability*0.9/count);
            child.set(indices[k],2);
            result+=0.1*player(child,depth-1,probability*0.1/count);
        }
        result/=count;
        e.board=b; e.value=result; e.depth=depth; e.probability=bits; e.generation=generation;
        return result;
    }
    double player(const Board& b,int depth,double probability) {
        double best=LOSS;
        for(int d=0;d<4;d++) {
            Board next=move(b,d);
            if(!(next==b)) best=std::max(best,chance(next,depth,probability));
        }
        // LOSS denotes an INVALID action, not a probabilistic game-over
        // utility. Using -1e12 for death overwhelms the ~1e6 heuristic even
        // for extremely unlikely spawns and destroys the intended policy.
        return best==LOSS ? terminalLoss : best;
    }
};
thread_local Search search;
Board from(const uint8_t* cells) { Board b; for(int i=0;i<16;i++) b.set(i,cells[i]); return b; }
}

// Directions: 0 up, 1 down, 2 left, 3 right. Ranks, not tile values.
API int ai_move(const uint8_t* cells,int direction,uint8_t* output) {
    std::call_once(initialized,init);
    if(direction<0 || direction>3) return -1;
    for(int i=0;i<16;i++) if(cells[i]>30) return -1;
    Board b=from(cells), result=move(b,direction);
    for(int i=0;i<16;i++) output[i]=result.at(i);
    return !(result==b);
}

API int ai_choose(const uint8_t* cells,int budget_ms,int max_depth,double cutoff,int target_rank,
                  double* values,uint64_t* stats) {
    std::call_once(initialized,init);
    for(int i=0;i<16;i++) if(cells[i]>30) return -2;
    Board b=from(cells);
    auto start=std::chrono::steady_clock::now();
    search.nodes=search.hits=0;
    search.cutoff=std::clamp(cutoff,1e-8,0.01);
    search.targetRank=std::clamp(target_rank,2,30);
    search.checkGoal=false;
    for(int i=0;i<16;i++) if(cells[i]>=search.targetRank-2) search.checkGoal=true;
    // Keep the upstream zero loss utility for normal boards, while allowing
    // signed heuristics on unusually high-rank input boards.
    search.terminalLoss=std::min(0.0,heuristic(b)-1600000.0);
    search.deadline=start+std::chrono::milliseconds(std::clamp(budget_ms,1,60000));
    if(++search.generation==0) { for(auto& e:search.cache)e.generation=0; search.generation=1; }
    int best=-1, completed=0;
    double bestscore=LOSS;
    // A complete, cheap baseline guarantees a legal answer even on timeout.
    for(int d=0;d<4;d++) {
        Board next=move(b,d);
        values[d]=next==b ? LOSS : heuristic(next);
        if(!(next==b) && search.checkGoal) {
            for(int i=0;i<16;i++) if(next.at(i)>=unsigned(search.targetRank)) {
                values[d]=WIN;
                stats[0]=stats[1]=stats[2]=stats[3]=0;
                // Populate the remaining entries before returning.
                for(int j=d+1;j<4;j++) {
                    Board other=move(b,j);
                    values[j]=other==b ? LOSS : heuristic(other);
                }
                return d;
            }
        }
        if(!(next==b) && (best<0 || values[d]>bestscore)) { best=d; bestscore=values[d]; }
    }
    if(best>=0) {
        for(int depth=1;depth<=std::clamp(max_depth,1,12);depth++) {
            double round[4]; int candidate=-1; double score=LOSS;
            try {
                for(int d=0;d<4;d++) {
                    Board next=move(b,d);
                    round[d]=next==b ? LOSS : search.chance(next,depth,1.0);
                    if(!(next==b) && (candidate<0 || round[d]>score)) { score=round[d]; candidate=d; }
                }
            } catch(const Timeout&) { break; }
            // Commit only complete rounds, so move order cannot bias timeout.
            std::copy(round,round+4,values); best=candidate; completed=depth;
            if(std::chrono::steady_clock::now()>=search.deadline) break;
        }
    }
    stats[0]=search.nodes; stats[1]=search.hits; stats[2]=completed;
    stats[3]=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count();
    return best;
}
