@{profile_scaled_checked_algorithm_definitions}

@{profile_unchecked_algorithm_aliases}

@{profile_docs_aggregate_selected_unary}
@{profile_algorithm_declaration_aggregate_selected_unary_checked}
        crate::tsl_algorithm::aggregate_selected_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        )
    }
@{profile_algorithm_declaration_aggregate_selected_unary_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, selected_count,
            )
        }
    }

@{profile_algorithm_declaration_aggregate_selected_unary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, selected_count)
        }
    }

@{profile_docs_aggregate_selected_binary}
@{profile_algorithm_declaration_aggregate_selected_binary_checked}
        crate::tsl_algorithm::aggregate_selected_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        )
    }

@{profile_algorithm_declaration_aggregate_selected_binary_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, selected_count,
            )
        }
    }

@{profile_algorithm_declaration_aggregate_selected_binary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, selected_count)
        }
    }


@{profile_algorithm_declaration_aggregate_unary}
        crate::tsl_algorithm::aggregate_unary::<Profile, Policy, Op, T>(
            policy, op, input,
        )
    }

@{profile_algorithm_declaration_aggregate_unary_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, count,
            )
        }
    }

@{profile_docs_aggregate_binary}
@{profile_algorithm_declaration_aggregate_binary_checked}
        crate::tsl_algorithm::aggregate_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right,
        )
    }

@{profile_algorithm_declaration_aggregate_binary_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, count,
            )
        }
    }

@{profile_docs_aggregate_masked_unary}
@{profile_algorithm_declaration_aggregate_masked_unary_checked}
        crate::tsl_algorithm::aggregate_masked_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        )
    }

@{profile_algorithm_declaration_aggregate_masked_unary_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            )
        }
    }

@{profile_docs_aggregate_masked_binary}
@{profile_algorithm_declaration_aggregate_masked_binary_checked}
        crate::tsl_algorithm::aggregate_masked_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        )
    }

@{profile_algorithm_declaration_aggregate_masked_binary_raw}
        unsafe {
            crate::tsl_algorithm::aggregate_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            )
        }
    }
