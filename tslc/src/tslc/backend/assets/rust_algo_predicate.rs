@{profile_unchecked_algorithm_aliases}

@{profile_docs_predicate_unary}
@{profile_algorithm_declaration_predicate_unary_checked}
        crate::tsl_algorithm::predicate_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        )
    }
@{profile_algorithm_declaration_predicate_unary_raw}
        unsafe {
            crate::tsl_algorithm::predicate_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            )
        }
    }

@{profile_docs_predicate_binary}
@{profile_algorithm_declaration_predicate_binary_checked}
        crate::tsl_algorithm::predicate_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        )
    }

@{profile_algorithm_declaration_predicate_binary_raw}
        unsafe {
            crate::tsl_algorithm::predicate_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            )
        }
    }

@{profile_docs_predicate_unary_mask_layout}
@{profile_algorithm_declaration_predicate_unary_mask_layout_checked}
        crate::tsl_algorithm::predicate_unary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks)
    }

@{profile_algorithm_declaration_predicate_unary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::predicate_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, count)
        }
    }

@{profile_docs_predicate_binary_mask_layout}
@{profile_algorithm_declaration_predicate_binary_mask_layout_checked}
        crate::tsl_algorithm::predicate_binary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks)
    }

@{profile_algorithm_declaration_predicate_binary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::predicate_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, count)
        }
    }
