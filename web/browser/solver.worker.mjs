// SPDX-License-Identifier: Apache-2.0
import createModule from '../solver.mjs';
import {createSolver} from './wasm-client.mjs';

let solver;
try {
  solver = await createSolver(createModule);
  self.postMessage({ready: true});
} catch (error) {
  self.postMessage({fatal: `浏览器引擎加载失败：${error.message}`});
}
self.onmessage = ({data}) => {
  try {
    if (!solver) throw new Error('引擎尚未就绪');
    self.postMessage({id: data.id, result: solver.choose(data.board, data.options)});
  } catch (error) {
    self.postMessage({id: data.id, error: error.message || String(error)});
  }
};
