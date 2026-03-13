# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
from libc.stdint cimport uint32_t, int32_t, uint8_t
from libc.string cimport memcpy
import cython

cdef extern from "openssl/sha.h" nogil:
    unsigned char *SHA256(const unsigned char *d, size_t n, unsigned char *md)

cdef inline int check_target(unsigned char* hash_bytes, const unsigned char* target_bytes) nogil:
    cdef int i
    cdef unsigned char h_byte, t_byte
    
    for i in range(32):
        h_byte = hash_bytes[i] 
        t_byte = target_bytes[i]
        
        if h_byte < t_byte: return 1
        if h_byte > t_byte: return 0
        
    return 0

@cython.boundscheck(False)
@cython.wraparound(False)
def solve_cpu_cython(
    int[:] miner_ids,            # int32 array
    int[:] max_qs,               # int32 array
    unsigned int[:] nonce_states,# uint32 array
    unsigned char[:] prehashes,  # uint8 array flat
    const unsigned char[:] target_bytes, # uint8 array 32 (Big Endian)
    unsigned int start_round,
    unsigned int total_rounds
):
    cdef int num_miners = miner_ids.shape[0]
    cdef int i, q
    cdef unsigned int r, current_round, current_nonce, base_nonce
    cdef int miner_id, mq
    cdef unsigned char hash_out[32]
    cdef unsigned char buffer[44]
    
    # Pointers for raw access
    cdef const unsigned char* t_ptr = &target_bytes[0]
    cdef unsigned char* ph_ptr = &prehashes[0]
    
    with nogil:
        for r in range(total_rounds):
            current_round = start_round + r
            
            for i in range(num_miners):
                miner_id = miner_ids[i]
                mq = max_qs[i]
                base_nonce = nonce_states[i]

                # Fill Buffer (44 bytes)
                # ID (4)
                buffer[0] = miner_id & 0xFF
                buffer[1] = (miner_id >> 8) & 0xFF
                buffer[2] = (miner_id >> 16) & 0xFF
                buffer[3] = (miner_id >> 24) & 0xFF
                
                # Round (4)
                buffer[4] = current_round & 0xFF
                buffer[5] = (current_round >> 8) & 0xFF
                buffer[6] = (current_round >> 16) & 0xFF
                buffer[7] = (current_round >> 24) & 0xFF
                
                # Prehash (32) - Prehash starts at i*32
                memcpy(&buffer[8], &ph_ptr[i * 32], 32)
                
                for q in range(mq):
                    current_nonce = base_nonce + q + 1
                    
                    # Nonce (4)
                    buffer[40] = current_nonce & 0xFF
                    buffer[41] = (current_nonce >> 8) & 0xFF
                    buffer[42] = (current_nonce >> 16) & 0xFF
                    buffer[43] = (current_nonce >> 24) & 0xFF
                    
                    # Hash
                    SHA256(&buffer[0], 44, &hash_out[0])
                    
                    # Check
                    if check_target(&hash_out[0], t_ptr):
                        with gil:
                            return (current_round, miner_id, current_nonce)
                
                # Update State
                nonce_states[i] = base_nonce + mq

    return None
