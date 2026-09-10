@{profile_docs_transform_unary}
@{profile_algorithm_declaration_transform_unary_checked}
        crate::tsl_algorithm::transform_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, output,
        )
    }
@{profile_algorithm_declaration_transform_unary_raw}
        unsafe {
            crate::tsl_algorithm::transform_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, output, count,
            );
        }
    }

@{profile_docs_transform_binary}
@{profile_algorithm_declaration_transform_binary_checked}
        crate::tsl_algorithm::transform_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, output,
        )
    }

@{profile_algorithm_declaration_transform_binary_raw}
        unsafe {
            crate::tsl_algorithm::transform_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, output, count,
            );
        }
    }

@{profile_scaled_checked_algorithm_definitions}

@{profile_unchecked_algorithm_aliases}

@{profile_docs_transform_selected_unary}
@{profile_algorithm_declaration_transform_selected_unary_checked}
        crate::tsl_algorithm::transform_selected_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, indices, output,
        )
    }

@{profile_algorithm_declaration_transform_selected_unary_raw}
        unsafe {
            crate::tsl_algorithm::transform_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, output, selected_count,
            );
        }
    }

@{profile_algorithm_declaration_transform_selected_unary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::transform_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, output, selected_count);
        }
    }

@{profile_docs_transform_selected_binary}
@{profile_algorithm_declaration_transform_selected_binary_checked}
        crate::tsl_algorithm::transform_selected_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, indices, output,
        )
    }

@{profile_algorithm_declaration_transform_selected_binary_raw}
        unsafe {
            crate::tsl_algorithm::transform_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, output, selected_count,
            );
        }
    }

@{profile_algorithm_declaration_transform_selected_binary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::transform_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, output, selected_count);
        }
    }


@{profile_docs_transform_where_unary}
@{profile_algorithm_declaration_transform_where_unary_checked}
        crate::tsl_algorithm::transform_where_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks, output,
        )
    }

@{profile_algorithm_declaration_transform_where_unary_raw}
        unsafe {
            crate::tsl_algorithm::transform_where_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, output, count,
            );
        }
    }

@{profile_docs_transform_where_unary_mask_layout}
@{profile_algorithm_declaration_transform_where_unary_mask_layout_checked}
        crate::tsl_algorithm::transform_where_unary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks, output)
    }

@{profile_algorithm_declaration_transform_where_unary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::transform_where_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, output, count);
        }
    }

@{profile_docs_transform_where_binary}
@{profile_algorithm_declaration_transform_where_binary_checked}
        crate::tsl_algorithm::transform_where_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, output,
        )
    }

@{profile_algorithm_declaration_transform_where_binary_raw}
        unsafe {
            crate::tsl_algorithm::transform_where_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, output, count,
            );
        }
    }

@{profile_docs_transform_where_binary_mask_layout}
@{profile_algorithm_declaration_transform_where_binary_mask_layout_checked}
        crate::tsl_algorithm::transform_where_binary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks, output)
    }

@{profile_algorithm_declaration_transform_where_binary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::transform_where_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, output, count);
        }
    }

@{profile_docs_transform_masked_unary}
@{profile_algorithm_declaration_transform_masked_unary_checked}
        crate::tsl_algorithm::transform_masked_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks, output,
        )
    }

@{profile_algorithm_declaration_transform_masked_unary_raw}
        unsafe {
            crate::tsl_algorithm::transform_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, output, count,
            );
        }
    }

@{profile_docs_transform_masked_binary}
@{profile_algorithm_declaration_transform_masked_binary_checked}
        crate::tsl_algorithm::transform_masked_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks, output,
        )
    }

@{profile_algorithm_declaration_transform_masked_binary_raw}
        unsafe {
            crate::tsl_algorithm::transform_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, output, count,
            );
        }
    }

@{profile_docs_transform_masked_unary_mask_layout}
@{profile_algorithm_declaration_transform_masked_unary_mask_layout_checked}
        crate::tsl_algorithm::transform_masked_unary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks, output)
    }

@{profile_algorithm_declaration_transform_masked_unary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::transform_masked_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, output, count);
        }
    }

@{profile_docs_transform_masked_binary_mask_layout}
@{profile_algorithm_declaration_transform_masked_binary_mask_layout_checked}
        crate::tsl_algorithm::transform_masked_binary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks, output)
    }

@{profile_algorithm_declaration_transform_masked_binary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::transform_masked_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, output, count);
        }
    }
