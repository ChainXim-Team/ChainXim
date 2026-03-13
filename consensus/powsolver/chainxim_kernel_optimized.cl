// ChainXim SHA-256 Mining Kernel Optimized

#define ROR(x, y) ((x >> y) | (x << (32 - y)))
#define Ch(x, y, z) ((x & y) ^ (~x & z))
#define Maj(x, y, z) ((x & y) ^ (x & z) ^ (y & z))
#define S0(x) (ROR(x, 2) ^ ROR(x, 13) ^ ROR(x, 22))
#define S1(x) (ROR(x, 6) ^ ROR(x, 11) ^ ROR(x, 25))
#define s0(x) (ROR(x, 7) ^ ROR(x, 18) ^ (x >> 3))
#define s1(x) (ROR(x, 17) ^ ROR(x, 19) ^ (x >> 10))

__constant uint K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

bool check_target_opt(uint* state, __constant const uint* target_words) {
    for (int i = 0; i <= 7; i++) {
        uint h_word = state[i]; 
        uint t_word = target_words[i];

        if (h_word < t_word) return true;
        if (h_word > t_word) return false;
    }
    return false; // Equal
}

__kernel void search_chainxim(
    __global const int* miner_ids,        
    __global const uint* prehashes,      
    __global uint* nonce_states,           
    __global const int* max_qs,           
    __constant const uint* target,   
    __global volatile uint* output_buffer, 
    __global volatile int* stop_flag,        
    uint start_round,
    uint total_rounds,
    int max_solutions,
    __global volatile int* best_round // Global Best Round Tracker
) {
    // 2D Work Item: (Miner, Round)
    int miner_id_idx = get_global_id(0);
    uint r_offset = get_global_id(1);

    int miner_id = miner_ids[miner_id_idx];
    // Calculate current round for this thread
    uint current_round = start_round + r_offset;

    // Optimization: Stop if we are already searching a round higher than the best found
    // Strict > check: If we are at round 100, and best is 100, we keep searching (to find concurrent miner)
    // If best is 99, we stop.
    if (current_round > best_round[0]) return; 
    
    // Global stop flag (Manual intervention)
    if (stop_flag[0] != 0) return;

    uint start_nonce_base_batch = nonce_states[miner_id_idx];
    int max_q = max_qs[miner_id_idx];
    
    // Derive start nonce for this round
    // Nonce[Round] = Base + RoundOffset * MaxQ
    uint start_nonce_base = start_nonce_base_batch + r_offset * max_q;
    
    uint W[64];
    uint mid_state[8];
    uint state[8];
    
    // 1. Miner ID
    W[0] = ((miner_id & 0xFF) << 24) | (((miner_id >> 8) & 0xFF) << 16) | 
            (((miner_id >> 16) & 0xFF) << 8) | ((miner_id >> 24) & 0xFF);
    
    // 2. Round/Content
    W[1] = ((current_round & 0xFF) << 24) | (((current_round >> 8) & 0xFF) << 16) | 
            (((current_round >> 16) & 0xFF) << 8) | ((current_round >> 24) & 0xFF);
    
    // 3. Prehash (W[2]..W[9])
    #pragma unroll
    for (int w=0; w<8; w++) W[2+w] = prehashes[miner_id_idx*8+w];
        
    // Padding
    W[11] = 0x80000000;
    W[12] = 0; W[13] = 0; W[14] = 0;
    W[15] = 352;
    
    W[16] = s1(W[14]) + W[9] + s0(W[1]) + W[0];

    state[0] = 0x6a09e667; state[1] = 0xbb67ae85; state[2] = 0x3c6ef372; state[3] = 0xa54ff53a;
    state[4] = 0x510e527f; state[5] = 0x9b05688c; state[6] = 0x1f83d9ab; state[7] = 0x5be0cd19;

    uint a=state[0], b=state[1], c=state[2], d=state[3], e=state[4], f=state[5], g=state[6], h=state[7];

    #pragma unroll
    for (int i = 0; i < 10; i++) {
        uint T1 = h + S1(e) + Ch(e, f, g) + K[i] + W[i];
        uint T2 = S0(a) + Maj(a, b, c);
        h=g; g=f; f=e; e=d+T1; d=c; c=b; b=a; a=T1+T2;
    }

    mid_state[0]=a; mid_state[1]=b; mid_state[2]=c; mid_state[3]=d; 
    mid_state[4]=e; mid_state[5]=f; mid_state[6]=g; mid_state[7]=h;

    // Nonce Loop (Check max_q nonces for this round)    
    for (int q = 0; q < max_q; q++) {
        uint current_nonce = start_nonce_base + q + 1;
        
        a=mid_state[0]; b=mid_state[1]; c=mid_state[2]; d=mid_state[3]; 
        e=mid_state[4]; f=mid_state[5]; g=mid_state[6]; h=mid_state[7];
        
        W[10] = ((current_nonce & 0xFF) << 24) | (((current_nonce >> 8) & 0xFF) << 16) | 
                (((current_nonce >> 16) & 0xFF) << 8) | ((current_nonce >> 24) & 0xFF);

        #pragma unroll
        for (int i = 17; i < 64; i++) {
            W[i] = s1(W[i-2]) + W[i-7] + s0(W[i-15]) + W[i-16];
        }

        #pragma unroll
        for (int i = 10; i < 64; i++) {
            uint T1 = h + S1(e) + Ch(e, f, g) + K[i] + W[i];
            uint T2 = S0(a) + Maj(a, b, c);
            h=g; g=f; f=e; e=d+T1; d=c; c=b; b=a; a=T1+T2;
        }

        state[0] = 0x6a09e667 + a;
        state[1] = 0xbb67ae85 + b;
        state[2] = 0x3c6ef372 + c;
        state[3] = 0xa54ff53a + d;
        state[4] = 0x510e527f + e;
        state[5] = 0x9b05688c + f;
        state[6] = 0x1f83d9ab + g;
        state[7] = 0x5be0cd19 + h;
        
        if (check_target_opt(state, target)) {
            // Update Global Best Round (Atomic Min)
            atomic_min(best_round, current_round);
            
            // Still save to output buffer
            uint idx = atomic_inc((volatile __global uint*)&output_buffer[0]);
            if (idx < max_solutions) {
                int out_off = 1 + idx * 11;
                output_buffer[out_off] = current_round;
                output_buffer[out_off + 1] = miner_id;
                output_buffer[out_off + 2] = current_nonce;
                
                #pragma unroll
                for(int k=0; k<8; k++) output_buffer[out_off + 3 + k] = state[k];
            }
            return;
        }
    }
}