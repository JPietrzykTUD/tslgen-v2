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

@{profile_algorithm_declaration_integral_mask_chunk_count}
        crate::tsl_algorithm::integral_mask_chunk_count::<Profile, Policy, T>(
            policy, count,
        )
    }

@{profile_algorithm_declaration_mask_chunk_count}
        crate::tsl_algorithm::mask_chunk_count::<Profile, Policy, Layout, T>(
            policy, count,
        )
    }

@{profile_algorithm_declaration_native_mask_chunk_count}
        crate::tsl_algorithm::native_mask_chunk_count::<Profile, Policy, T>(
            policy, count,
        )
    }

@{profile_algorithm_declaration_byte_mask_count}
        crate::tsl_algorithm::byte_mask_count::<Profile, Policy, T>(
            policy, count,
        )
    }

@{profile_algorithm_declaration_bit_mask_count}
        crate::tsl_algorithm::bit_mask_count::<Profile, Policy, T>(
            policy, count,
        )
    }

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

@{profile_algorithm_declaration_count_unary}
        crate::tsl_algorithm::count_unary::<Profile, Policy, Op, T>(
            policy, op, input,
        )
    }

@{profile_algorithm_declaration_count_unary_raw}
        unsafe {
            crate::tsl_algorithm::count_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, count,
            )
        }
    }

@{profile_docs_count_binary}
@{profile_algorithm_declaration_count_binary_checked}
        crate::tsl_algorithm::count_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right,
        )
    }

@{profile_algorithm_declaration_count_binary_raw}
        unsafe {
            crate::tsl_algorithm::count_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, count,
            )
        }
    }

@{profile_docs_count_masked_unary}
@{profile_algorithm_declaration_count_masked_unary_checked}
        crate::tsl_algorithm::count_masked_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        )
    }

@{profile_algorithm_declaration_count_masked_unary_raw}
        unsafe {
            crate::tsl_algorithm::count_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            )
        }
    }

@{profile_docs_count_masked_binary}
@{profile_algorithm_declaration_count_masked_binary_checked}
        crate::tsl_algorithm::count_masked_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        )
    }

@{profile_algorithm_declaration_count_masked_binary_raw}
        unsafe {
            crate::tsl_algorithm::count_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            )
        }
    }

@{profile_docs_count_masked_unary_mask_layout}
@{profile_algorithm_declaration_count_masked_unary_mask_layout_checked}
        crate::tsl_algorithm::count_masked_unary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, input, masks)
    }

@{profile_algorithm_declaration_count_masked_unary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::count_masked_unary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, input, masks, count)
        }
    }

@{profile_docs_count_masked_binary_mask_layout}
@{profile_algorithm_declaration_count_masked_binary_mask_layout_checked}
        crate::tsl_algorithm::count_masked_binary_mask_layout_checked::<
            Profile,
            Policy,
            Layout,
            Op,
            T,
        >(policy, op, left, right, masks)
    }

@{profile_algorithm_declaration_count_masked_binary_mask_layout_raw}
        unsafe {
            crate::tsl_algorithm::count_masked_binary_mask_layout_raw::<
                Profile,
                Policy,
                Layout,
                Op,
                T,
            >(policy, op, left, right, masks, count)
        }
    }

@{profile_docs_count_selected_unary}
@{profile_algorithm_declaration_count_selected_unary_checked}
        crate::tsl_algorithm::count_selected_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        )
    }

@{profile_algorithm_declaration_count_selected_unary_raw}
        unsafe {
            crate::tsl_algorithm::count_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, selected_count,
            )
        }
    }

@{profile_algorithm_declaration_count_selected_unary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::count_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, selected_count)
        }
    }

@{profile_docs_count_selected_binary}
@{profile_algorithm_declaration_count_selected_binary_checked}
        crate::tsl_algorithm::count_selected_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        )
    }

@{profile_algorithm_declaration_count_selected_binary_raw}
        unsafe {
            crate::tsl_algorithm::count_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, selected_count,
            )
        }
    }

@{profile_algorithm_declaration_count_selected_binary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::count_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, selected_count)
        }
    }

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

@{profile_docs_consume_selected_unary}
@{profile_algorithm_declaration_consume_selected_unary_checked}
        crate::tsl_algorithm::consume_selected_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, indices,
        )
    }

@{profile_algorithm_declaration_consume_selected_unary_raw}
        unsafe {
            crate::tsl_algorithm::consume_selected_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, indices, selected_count,
            );
        }
    }

@{profile_algorithm_declaration_consume_selected_unary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::consume_selected_unary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, input, indices, selected_count);
        }
    }

@{profile_docs_consume_selected_binary}
@{profile_algorithm_declaration_consume_selected_binary_checked}
        crate::tsl_algorithm::consume_selected_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, indices,
        )
    }

@{profile_algorithm_declaration_consume_selected_binary_raw}
        unsafe {
            crate::tsl_algorithm::consume_selected_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, indices, selected_count,
            );
        }
    }

@{profile_algorithm_declaration_consume_selected_binary_scaled_raw}
        unsafe {
            crate::tsl_algorithm::consume_selected_binary_scaled_raw::<
                Profile,
                SCALE,
                Policy,
                Op,
                T,
            >(policy, op, left, right, indices, selected_count);
        }
    }

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

@{profile_algorithm_declaration_consume_unary}
        crate::tsl_algorithm::consume_unary::<Profile, Policy, Op, T>(
            policy, op, input,
        );
    }

@{profile_algorithm_declaration_consume_unary_raw}
        unsafe {
            crate::tsl_algorithm::consume_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, count,
            );
        }
    }

@{profile_docs_consume_binary}
@{profile_algorithm_declaration_consume_binary_checked}
        crate::tsl_algorithm::consume_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right,
        )
    }

@{profile_algorithm_declaration_consume_binary_raw}
        unsafe {
            crate::tsl_algorithm::consume_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, count,
            );
        }
    }

@{profile_docs_consume_masked_unary}
@{profile_algorithm_declaration_consume_masked_unary_checked}
        crate::tsl_algorithm::consume_masked_unary_checked::<Profile, Policy, Op, T>(
            policy, op, input, masks,
        )
    }

@{profile_algorithm_declaration_consume_masked_unary_raw}
        unsafe {
            crate::tsl_algorithm::consume_masked_unary_raw::<Profile, Policy, Op, T>(
                policy, op, input, masks, count,
            );
        }
    }

@{profile_docs_consume_masked_binary}
@{profile_algorithm_declaration_consume_masked_binary_checked}
        crate::tsl_algorithm::consume_masked_binary_checked::<Profile, Policy, Op, T>(
            policy, op, left, right, masks,
        )
    }

@{profile_algorithm_declaration_consume_masked_binary_raw}
        unsafe {
            crate::tsl_algorithm::consume_masked_binary_raw::<Profile, Policy, Op, T>(
                policy, op, left, right, masks, count,
            );
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
