@{profile_scaled_checked_algorithm_definitions}

@{profile_unchecked_algorithm_aliases}

@{profile_docs_select_unary}
@{profile_algorithm_declaration_select_unary_checked}
        crate::tsl_algorithm::select_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, output,
        )
    }

@{profile_algorithm_declaration_select_unary_raw}
        unsafe {
            crate::tsl_algorithm::select_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, output, count,
            )
        }
    }

@{profile_docs_select_binary}
@{profile_algorithm_declaration_select_binary_checked}
        crate::tsl_algorithm::select_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, output,
        )
    }

@{profile_algorithm_declaration_select_binary_raw}
        unsafe {
            crate::tsl_algorithm::select_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, output, count,
            )
        }
    }

@{profile_docs_select_masked_unary}
@{profile_algorithm_declaration_select_masked_unary_checked}
        crate::tsl_algorithm::select_masked_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks, output,
        )
    }

@{profile_algorithm_declaration_select_masked_unary_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, output, count,
            )
        }
    }

@{profile_docs_select_masked_binary}
@{profile_algorithm_declaration_select_masked_binary_checked}
        crate::tsl_algorithm::select_masked_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, output,
        )
    }

@{profile_algorithm_declaration_select_masked_binary_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, output, count,
            )
        }
    }

@{profile_docs_select_masked_unary_mask_layout}
@{profile_algorithm_declaration_select_masked_unary_mask_layout_checked}
        crate::tsl_algorithm::select_masked_unary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks, output)
    }

@{profile_algorithm_declaration_select_masked_unary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, output, count)
        }
    }

@{profile_docs_select_masked_binary_mask_layout}
@{profile_algorithm_declaration_select_masked_binary_mask_layout_checked}
        crate::tsl_algorithm::select_masked_binary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks, output)
    }

@{profile_algorithm_declaration_select_masked_binary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, output, count)
        }
    }

@{profile_docs_select_indices_unary}
@{profile_algorithm_declaration_select_indices_unary_checked}
        crate::tsl_algorithm::select_indices_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        )
    }

@{profile_algorithm_declaration_select_indices_unary_raw}
        unsafe {
            crate::tsl_algorithm::select_indices_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, count,
            )
        }
    }

@{profile_docs_select_indices_binary}
@{profile_algorithm_declaration_select_indices_binary_checked}
        crate::tsl_algorithm::select_indices_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        )
    }

@{profile_algorithm_declaration_select_indices_binary_raw}
        unsafe {
            crate::tsl_algorithm::select_indices_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, count,
            )
        }
    }

@{profile_docs_select_masked_indices_unary}
@{profile_algorithm_declaration_select_masked_indices_unary_checked}
        crate::tsl_algorithm::select_masked_indices_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks, indices,
        )
    }

@{profile_algorithm_declaration_select_masked_indices_unary_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_indices_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, indices, count,
            )
        }
    }

@{profile_docs_select_masked_indices_binary}
@{profile_algorithm_declaration_select_masked_indices_binary_checked}
        crate::tsl_algorithm::select_masked_indices_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, indices,
        )
    }

@{profile_algorithm_declaration_select_masked_indices_binary_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_indices_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, indices, count,
            )
        }
    }

@{profile_docs_select_masked_indices_unary_mask_layout}
@{profile_algorithm_declaration_select_masked_indices_unary_mask_layout_checked}
        crate::tsl_algorithm::select_masked_indices_unary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks, indices)
    }

@{profile_algorithm_declaration_select_masked_indices_unary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_indices_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, indices, count)
        }
    }

@{profile_docs_select_masked_indices_binary_mask_layout}
@{profile_algorithm_declaration_select_masked_indices_binary_mask_layout_checked}
        crate::tsl_algorithm::select_masked_indices_binary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks, indices)
    }

@{profile_algorithm_declaration_select_masked_indices_binary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::select_masked_indices_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, indices, count)
        }
    }

@{profile_docs_select_selected_indices_unary}
@{profile_algorithm_declaration_select_selected_indices_unary_checked}
        crate::tsl_algorithm::select_selected_indices_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, input_indices, output_indices,
        )
    }

@{profile_algorithm_declaration_select_selected_indices_unary_raw}
        unsafe {
            crate::tsl_algorithm::select_selected_indices_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, input_indices, output_indices, selected_count,
            )
        }
    }

@{profile_algorithm_declaration_select_selected_indices_unary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::select_selected_indices_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, input_indices, output_indices, selected_count)
        }
    }

@{profile_docs_select_selected_indices_binary}
@{profile_algorithm_declaration_select_selected_indices_binary_checked}
        crate::tsl_algorithm::select_selected_indices_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, input_indices, output_indices,
        )
    }

@{profile_algorithm_declaration_select_selected_indices_binary_raw}
        unsafe {
            crate::tsl_algorithm::select_selected_indices_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, input_indices, output_indices, selected_count,
            )
        }
    }

@{profile_algorithm_declaration_select_selected_indices_binary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::select_selected_indices_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(
                policy,
                op,
                left,
                right,
                input_indices,
                output_indices,
                selected_count,
            )
        }
    }
