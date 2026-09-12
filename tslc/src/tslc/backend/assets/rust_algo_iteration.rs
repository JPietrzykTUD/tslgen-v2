@{profile_algorithm_declaration_for_each_chunk}
        crate::tsl_algorithm::for_each_chunk::<Profile, Policy, Op, T>(
            policy, op, data,
        );
    }

@{profile_algorithm_declaration_for_each_chunk_raw}
        unsafe {
            crate::tsl_algorithm::for_each_chunk_raw::<Profile, Policy, Op, T>(
                policy, op, data, count,
            );
        }
    }
