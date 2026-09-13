import os
from typing import cast

import numpy as np

try:
    import pyopencl as cl
except ImportError:
    cl = None

from .pow import PoW

GPU_SELECTOR_ENV = "CHAINXIM_GPU_ID"
REQUIRE_GPU_ENV = "CHAINXIM_REQUIRE_GPU"
MAX_SEARCH_ROUND = 0xFFFFFFFF


def _search_window(start_round: int, total_rounds: int) -> int:
    if not 0 <= start_round <= MAX_SEARCH_ROUND:
        raise OverflowError(
            f"FastPoW round {start_round} exceeds the 4-byte round range "
            f"0..{MAX_SEARCH_ROUND}"
        )
    if total_rounds <= 0:
        raise ValueError("FastPoW search length must be positive")
    return min(total_rounds, MAX_SEARCH_ROUND - start_round + 1)


def _require_gpu() -> bool:
    return os.environ.get(REQUIRE_GPU_ENV, "").lower() in {"1", "true", "yes"}


def list_gpu_devices() -> list[dict[str, object]]:
    """Return flattened OpenCL GPU IDs used by the batch experiment runner."""
    if cl is None:
        return []

    devices: list[dict[str, object]] = []
    for platform_id, platform in enumerate(cl.get_platforms()):
        for device_id, device in enumerate(platform.get_devices(device_type=cl.device_type.GPU)):
            devices.append(
                {
                    "id": len(devices),
                    "platform_id": platform_id,
                    "device_id": device_id,
                    "platform": platform.name,
                    "name": device.name,
                }
            )
    return devices


def _select_gpu(selector: str):
    devices = list_gpu_devices()
    if ":" in selector:
        try:
            platform_id, device_id = (int(part) for part in selector.split(":", 1))
        except ValueError as exc:
            raise ValueError(
                f"{GPU_SELECTOR_ENV} must be a flattened integer ID or platform:device"
            ) from exc
        matches = [
            item
            for item in devices
            if item["platform_id"] == platform_id and item["device_id"] == device_id
        ]
    else:
        try:
            flattened_id = int(selector)
        except ValueError as exc:
            raise ValueError(
                f"{GPU_SELECTOR_ENV} must be a flattened integer ID or platform:device"
            ) from exc
        matches = [item for item in devices if item["id"] == flattened_id]

    if len(matches) != 1:
        available = ", ".join(
            f"{item['id']}={item['platform_id']}:{item['device_id']} {item['name']}"
            for item in devices
        ) or "none"
        raise RuntimeError(f"GPU selector {selector!r} is unavailable; available GPUs: {available}")
    match = matches[0]
    platforms = cl.get_platforms()
    platform_id = cast(int, match["platform_id"])
    device_id = cast(int, match["device_id"])
    return platforms[platform_id].get_devices(
        device_type=cl.device_type.GPU
    )[device_id], match


class FastPoW(PoW):
    has_fast_track = True

    class PoWFastTrack:
        def __init__(self, consensus_collection: list['FastPoW']):
            self.consensus_collection = consensus_collection
            self.STEP = 1000
            
            # Worker 通过环境变量固定一个 OpenCL GPU；未设置时保留旧的 0 号选择。
            self.device_id = os.environ.get(GPU_SELECTOR_ENV, "0")
            self.require_gpu = _require_gpu()
            self.gpu_info = None
            self.ctx = None
            self.queue = None
            self.program = None
            self.kernel = None
            self.target = consensus_collection[0].target
            self.ids_np = np.array([m.miner_id for m in self.consensus_collection], dtype=np.int32)
            self.max_qs_np = np.array([m.q for m in self.consensus_collection], dtype=np.int32)
            
            try:
                if cl is None:
                    raise RuntimeError("pyopencl is not installed")
                dev, self.gpu_info = _select_gpu(self.device_id)
                self.device_type = 'gpu'
                self.ctx = cl.Context([dev])
                self.queue = cl.CommandQueue(self.ctx)
                self._init_opencl()
            except Exception as e:
                if self.require_gpu:
                    raise RuntimeError(
                        f"FastPoW GPU is required, but selector {self.device_id!r} failed"
                    ) from e
                print(f"OpenCL init failed, fallback to CPU solver: {e}")
                self.device_type = 'cpu'

            try:
                from .powsolver import cpu_solver
                self.cpu_module = cpu_solver
            except ImportError:
                self.cpu_module = None
                if self.device_type == 'cpu':
                    print("cpu_solver module not found, FastPoW will not work.")
                    self.consensus_collection = None
            
            # Buffers for GPU
            if self.device_type == 'gpu':
                 self._alloc_gpu_buffers()

        def _init_opencl(self):
            # Load kernel
            path = os.path.join(os.path.dirname(__file__), 'powsolver/chainxim_kernel_optimized.cl')
            if not os.path.exists(path):
                raise FileNotFoundError(f"Kernel file not found at {path}")
            
            with open(path, 'r') as f:
                src = f.read()
            self.program = cl.Program(self.ctx, src).build()
            self.kernel = cl.Kernel(self.program, 'search_chainxim')
            
        def _alloc_gpu_buffers(self):
            # Pre-allocate large buffers to avoid re-allocating every round
            # Let's allocate based on current collection size
            num = len(self.consensus_collection)
            mf = cl.mem_flags
            
            self.h_ids = np.zeros(num, dtype=np.int32)
            self.h_max_qs = np.zeros(num, dtype=np.int32)
            for i, m in enumerate(self.consensus_collection):
                self.h_ids[i] = m.miner_id
                self.h_max_qs[i] = m.q
            self.h_prehash = np.zeros(num * 8, dtype=np.uint32)
            self.h_nonce_states = np.zeros(num, dtype=np.uint32)
            # Big-endian uint32 conversion for SHA256
            self.h_target = np.frombuffer(self.target, dtype='>u4').astype(np.uint32)
            self.h_output = np.zeros(1 + 100 * 11, dtype=np.uint32)
            self.h_stop_flag = np.zeros(1, dtype=np.int32)
            self.h_best_round = np.zeros(1, dtype=np.uint32)
            
            self.buf_ids = cl.Buffer(self.ctx, mf.READ_ONLY, size=self.h_ids.nbytes)
            self.buf_prehash = cl.Buffer(self.ctx, mf.READ_ONLY, size=self.h_prehash.nbytes)
            self.buf_max_qs = cl.Buffer(self.ctx, mf.READ_ONLY, size=self.h_max_qs.nbytes)
            self.buf_nonce_states = cl.Buffer(self.ctx, mf.READ_WRITE, size=self.h_nonce_states.nbytes)
            self.buf_target = cl.Buffer(self.ctx, mf.READ_ONLY, size=self.h_target.nbytes)
            self.buf_output = cl.Buffer(self.ctx, mf.READ_WRITE, size=self.h_output.nbytes)
            self.buf_stop_flag = cl.Buffer(self.ctx, mf.READ_ONLY, size=self.h_stop_flag.nbytes)
            self.buf_best_round = cl.Buffer(self.ctx, mf.READ_WRITE, size=self.h_best_round.nbytes)
            
            self.max_solutions = 100

        def solve_gpu(self, start_round: int, total_rounds: int):
            total_rounds = _search_window(start_round, total_rounds)
            num = len(self.consensus_collection)

            # Load Data
            for i, m in enumerate(self.consensus_collection):
                # self.h_ids[i] = m.miner_id
                # self.h_max_qs[i] = m.q
                self.h_nonce_states[i] = m.ctr
                p_bytes = m.local_chain.last_block.blockhash
                if len(p_bytes) < 32: p_bytes += b'\x00' * (32 - len(p_bytes))
                # Big-endian uint32 conversion for SHA256
                self.h_prehash[i*8 : i*8+8] = np.frombuffer(p_bytes[:32], dtype='>u4').astype(np.uint32)

            self.h_stop_flag[0] = 0
            self.h_output[0] = 0
            self.h_best_round[0] = MAX_SEARCH_ROUND

            cl.enqueue_copy(self.queue, self.buf_ids, self.h_ids[:num])
            cl.enqueue_copy(self.queue, self.buf_prehash, self.h_prehash[:num*8])
            cl.enqueue_copy(self.queue, self.buf_max_qs, self.h_max_qs[:num])
            cl.enqueue_copy(self.queue, self.buf_nonce_states, self.h_nonce_states[:num])
            cl.enqueue_copy(self.queue, self.buf_target, self.h_target)
            cl.enqueue_copy(self.queue, self.buf_stop_flag, self.h_stop_flag)
            cl.enqueue_copy(self.queue, self.buf_output, self.h_output)
            cl.enqueue_copy(self.queue, self.buf_best_round, self.h_best_round)

            self.kernel.set_arg(0, self.buf_ids)
            self.kernel.set_arg(1, self.buf_prehash)
            self.kernel.set_arg(2, self.buf_nonce_states)
            self.kernel.set_arg(3, self.buf_max_qs)
            self.kernel.set_arg(4, self.buf_target)
            self.kernel.set_arg(5, self.buf_output)
            self.kernel.set_arg(6, self.buf_stop_flag)
            self.kernel.set_arg(7, np.uint32(start_round))
            self.kernel.set_arg(8, np.uint32(total_rounds))
            self.kernel.set_arg(9, np.int32(self.max_solutions))
            self.kernel.set_arg(10, self.buf_best_round)

            evt = cl.enqueue_nd_range_kernel(self.queue, self.kernel, (num, total_rounds), None)
            evt.wait()

            cl.enqueue_copy(self.queue, self.h_output, self.buf_output)
            
            count = self.h_output[0]
            if count > 0:
                valid_count = min(count, self.max_solutions)
                solutions = []
                for i in range(valid_count):
                    off = 1 + i*11
                    rnd = int(self.h_output[off])
                    mid = int(self.h_output[off+1])
                    nonce = int(self.h_output[off+2])
                    solutions.append((rnd, mid, nonce))
                
                solutions.sort(key=lambda x: x[0])
                # Return best solution
                return solutions[0]
            
            return None

        def solve_cpu(self, start_round: int, total_rounds: int):
            total_rounds = _search_window(start_round, total_rounds)
            num = len(self.consensus_collection)

            # Prepare arrays for Cython
            nonces_np = np.array([m.ctr for m in self.consensus_collection], dtype=np.uint32)
            
            prehashes_np = np.zeros(num * 32, dtype=np.uint8)
            for i, m in enumerate(self.consensus_collection):
                p = m.local_chain.last_block.blockhash
                if len(p) < 32: p += b'\x00' * (32 - len(p))
                prehashes_np[i*32:(i+1)*32] = np.frombuffer(p[:32], dtype=np.uint8)
            
            res = self.cpu_module.solve_cpu_cython(
                self.ids_np,
                self.max_qs_np,
                nonces_np,
                prehashes_np,
                self.target,
                start_round,
                total_rounds
            )

            # res is (round, miner_id, nonce) or None
            return res

        def run_fast_track(self, start_round: int) -> int:
            if not self.consensus_collection:
                return start_round
            
            current_round = start_round
            while True:
                search_rounds = _search_window(current_round, self.STEP)
                # Execute Solver
                if self.device_type == 'gpu':
                     result = self.solve_gpu(current_round, search_rounds)
                else:
                     result = self.solve_cpu(current_round, search_rounds)
                
                if result:
                    found_round, _winner_id, _winner_nonce = result
                    # Update States (Elapsed in this step)
                    elapsed = found_round - current_round
                    for m in self.consensus_collection:
                        m.ctr += elapsed * m.q
                    return found_round
                
                # No block found, advance states by the searched rounds.
                for m in self.consensus_collection:
                    m.ctr += search_rounds * m.q
                current_round += search_rounds

    @classmethod
    def get_fast_track(cls, miner_list, adver_ids, adver_consensus):
        collection = []
        for m in miner_list:
            if m.miner_id not in adver_ids and isinstance(m.consensus, FastPoW):
                collection.append(m.consensus)
        
        if adver_consensus:
            collection.append(adver_consensus)
                
        return cls.PoWFastTrack(collection)
