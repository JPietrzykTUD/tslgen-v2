# TSIL Type Query Inventory

Milestone 143 inventories and lowers the observed TSIL type language used by
the current `tsldata/**/*.tsl` corpus. The corpus ground truth is every
current `.tsl` file under `tsldata/`; `frozen/` is evidence only for semantic
clarification and is not a runtime dependency.

Survey scope:

- 41 current `.tsl` files under `tsldata/`.
- `let<type>(...)`: 382 occurrences, 39 unique normalized forms.
- `type<generation>(...)`: 1787 occurrences, 34 unique normalized forms.
- `type<backend>(...)`: 212 occurrences, 11 unique normalized forms.

The inventory below records normalized exact source forms, occurrence counts,
and one representative source location.

## Type Categories

M143 classifies observed forms into these semantic categories:

- Context-given generation types: `base::in`, `vector::register`,
  `vector::mask`, `vector::imask`, `vector::mask_underlying_t`,
  `vector::mask_underlying`, and `vector::offset_base`.
- Type transforms: `base::signed_of(...)`, `base::unsigned_of(...)`,
  `base::generic(...)`, `register::generic(...)`, `base::id(...)`,
  `vector::transform(...)`, `vector::transform_extension(...)`,
  `vector::as_extension(...)`, and the observed `select(...)` type form.
- Independent type identities: `size_t`, `intrin::vector::imask`, observed
  `scalar::...` backend type names, and bare scalar tags used as selected
  `select(...)` branches.
- Ordered source aliases: arbitrary source identifiers bound by preceding
  `let<type>(AliasName, TypeExpr)` directives in the same selected body.
- Specialization symbols: observed unbound type or extension symbols such as
  `ToBase`, `ToType`, and `ToExtension` when they appear as arguments to the
  supported type transforms. They are typed semantic symbols, not aliases and
  not backend text.

M169 update: selected targets may now supply explicit specialization binding
facts for those symbols. `ToBase`/`ToExtension` remain corpus examples:
return-type base/extension bindings validate against the primitive-local
`return_type` declaration, and focused tests also use arbitrary names such as
`ResultBase` and `TargetExtension`. An explicit vector/type binding can make
observed `ToType`-style `register::generic(ToType)` queries concrete without
deriving `ToType` from source branches.

M170 update: the same explicit selected binding facts are now visible to exact
bare primitive-call selector payload entries. This does not add a selector
tree parser; it only lets selector-payload lowering consume already supplied
base, extension, and vector/type facts.

## `let<type>(...)` Forms

| Count | Representative source | Form | Category |
| ---: | --- | --- | --- |
| 7 | `tsldata/primitives/conversion/repr_change.tsl:1513:19` | `let<type>(ChunkVec, type<generation>(vector::as_extension(avx2, ToBase)))` | alias to `vector::as_extension` |
| 10 | `tsldata/primitives/conversion/repr_change.tsl:1400:19` | `let<type>(ChunkVec, type<generation>(vector::as_extension(sse, ToBase)))` | alias to `vector::as_extension` |
| 1 | `tsldata/primitives/misc/conflict.tsl:73:15` | `let<type>(ConflictT, type<backend>(size_t))` | alias to backend type request |
| 1 | `tsldata/primitives/mask/bitwise.tsl:326:15` | `let<type>(CountT, type<generation>(vector::imask))` | alias to context vector member |
| 49 | `tsldata/primitives/arithmetic/complex.tsl:66:13` | `let<type>(GenericVec, type<backend>(vector::as_extension(generic)))` | alias to backend type request |
| 6 | `tsldata/primitives/conversion/repr_change.tsl:1524:19` | `let<type>(HalfVec, type<generation>(vector::as_extension(sse, ToBase)))` | alias to `vector::as_extension` |
| 2 | `tsldata/primitives/conversion/mask_specific.tsl:98:16` | `let<type>(ImaskT, type<generation>(vector::imask))` | alias to context vector member |
| 7 | `tsldata/primitives/load_store/pack_expand.tsl:281:20` | `let<type>(InVec, type<generation>(vector::as_extension(avx2, type<generation>(base::in))))` | alias to `vector::as_extension` |
| 11 | `tsldata/primitives/load_store/pack_expand.tsl:289:20` | `let<type>(InVec, type<generation>(vector::as_extension(sse, type<generation>(base::in))))` | alias to `vector::as_extension` |
| 2 | `tsldata/primitives/load_store/pack_expand.tsl:71:13` | `let<type>(IndexBase, type<generation>(base::unsigned_of(type<generation>(base::in))))` | alias to signedness transform |
| 2 | `tsldata/primitives/load_store/pack_expand.tsl:72:13` | `let<type>(IndexVec, type<generation>(vector::transform_extension(IndexBase)))` | alias to vector transform |
| 12 | `tsldata/primitives/load_store/sequence.tsl:25:13` | `let<type>(IntrinBase, type<generation>(base::signed_of(type<generation>(base::in))))` | alias to signedness transform |
| 20 | `tsldata/primitives/comparison/fundamental.tsl:39:13` | `let<type>(MaskT, type<generation>(vector::mask))` | alias to context vector member |
| 5 | `tsldata/primitives/comparison/fundamental.tsl:142:13` | `let<type>(MaskVec, type<generation>(vector::transform(type<generation>(base::unsigned_of(type<generation>(base::in))))))` | alias to vector transform |
| 1 | `tsldata/primitives/load_store/store.tsl:239:15` | `let<type>(MaskVec, type<generation>(vector::transform(type<generation>(vector::mask_underlying_t))))` | alias to vector transform |
| 1 | `tsldata/primitives/conversion/mask_specific.tsl:447:15` | `let<type>(MaskVec, type<generation>(vector::transform_extension(type<backend>(scalar::si32))))` | alias to vector transform over backend request |
| 1 | `tsldata/primitives/conversion/mask_specific.tsl:463:15` | `let<type>(MaskVec, type<generation>(vector::transform_extension(type<backend>(scalar::si64))))` | alias to vector transform over backend request |
| 3 | `tsldata/primitives/load_store/store.tsl:181:15` | `let<type>(MaskWord, type<generation>(vector::mask_underlying_t))` | alias to context vector member |
| 4 | `tsldata/primitives/conversion/repr_change.tsl:1682:15` | `let<type>(OutBase, type<generation>(base::generic(OutVec)))` | alias to generic-base projection |
| 6 | `tsldata/primitives/conversion/repr_change.tsl:121:19` | `let<type>(OutVec, type<generation>(vector::as_extension(ToExtension)))` | alias to `vector::as_extension` |
| 94 | `tsldata/primitives/conversion/cast.tsl:615:19` | `let<type>(OutVec, type<generation>(vector::transform_extension(ToBase)))` | alias to vector transform |
| 12 | `tsldata/primitives/comparison/fundamental.tsl:54:13` | `let<type>(RegisterT, type<generation>(vector::register))` | alias to context vector member |
| 15 | `tsldata/primitives/load_store/load.tsl:189:13` | `let<type>(SignedBase, type<generation>(base::signed_of(type<generation>(base::in))))` | alias to signedness transform |
| 5 | `tsldata/primitives/bitwise/shifts.tsl:1225:19` | `let<type>(SignedT, type<generation>(base::signed_of(type<generation>(base::in))))` | alias to signedness transform |
| 2 | `tsldata/primitives/bitwise/shifts.tsl:1226:19` | `let<type>(SignedVec, type<generation>(vector::transform_extension(SignedT)))` | alias to vector transform |
| 4 | `tsldata/primitives/conversion/cast.tsl:628:21` | `let<type>(StepVec, type<generation>(vector::transform_extension(type<backend>(scalar::si16))))` | alias to vector transform over backend request |
| 2 | `tsldata/primitives/conversion/cast.tsl:665:21` | `let<type>(StepVec, type<generation>(vector::transform_extension(type<backend>(scalar::si32))))` | alias to vector transform over backend request |
| 4 | `tsldata/primitives/conversion/cast.tsl:631:21` | `let<type>(StepVec, type<generation>(vector::transform_extension(type<backend>(scalar::ui16))))` | alias to vector transform over backend request |
| 2 | `tsldata/primitives/conversion/cast.tsl:668:21` | `let<type>(StepVec, type<generation>(vector::transform_extension(type<backend>(scalar::ui32))))` | alias to vector transform over backend request |
| 3 | `tsldata/primitives/conversion/mask_specific.tsl:221:16` | `let<type>(T, type<generation>(vector::register))` | alias to context vector member |
| 27 | `tsldata/primitives/conversion/repr_change.tsl:345:23` | `let<type>(To, type<generation>(base::generic(OutVec)))` | alias to generic-base projection |
| 9 | `tsldata/primitives/conversion/cast.tsl:754:21` | `let<type>(UBase, type<generation>(base::unsigned_of(type<generation>(base::in))))` | alias to signedness transform |
| 9 | `tsldata/primitives/conversion/cast.tsl:755:21` | `let<type>(UVec, type<generation>(vector::transform_extension(UBase)))` | alias to vector transform |
| 1 | `tsldata/primitives/conversion/mask_specific.tsl:274:15` | `let<type>(UVec, type<generation>(vector::transform_extension(UnsignedT)))` | alias to vector transform |
| 5 | `tsldata/primitives/bitwise/shifts.tsl:878:19` | `let<type>(UVec, type<generation>(vector::transform_extension(type<generation>(base::unsigned_of(type<generation>(base::in))))))` | alias to vector transform |
| 25 | `tsldata/primitives/bitwise/shifts.tsl:627:19` | `let<type>(UnsignedT, type<generation>(base::unsigned_of(type<generation>(base::in))))` | alias to signedness transform |
| 9 | `tsldata/primitives/bitwise/bit_counts.tsl:97:16` | `let<type>(UnsignedT, type<generation>(select(value<generation>(type::is_same(type<generation>(base::in), f32)), ui32, ui64)))` | alias to type select |
| 1 | `tsldata/primitives/load_store/construct.tsl:379:15` | `let<type>(Value, type<generation>(vector::register))` | alias to context vector member |
| 2 | `tsldata/primitives/io/out.tsl:38:16` | `let<type>(cast_type, type<generation>(base::in))` | alias to context scalar/base |

## `type<generation>(...)` Forms

| Count | Representative source | Form | Category |
| ---: | --- | --- | --- |
| 37 | `tsldata/primitives/conversion/cast.tsl:620:46` | `type<generation>(base::generic(OutVec))` | generic-base projection |
| 832 | `tsldata/primitives/arithmetic/complex.tsl:678:67` | `type<generation>(base::in)` | context scalar/base |
| 192 | `tsldata/primitives/arithmetic/complex.tsl:58:54` | `type<generation>(base::signed_of(type<generation>(base::in)))` | signedness transform |
| 161 | `tsldata/primitives/bitwise/bit_counts.tsl:53:46` | `type<generation>(base::unsigned_of(type<generation>(base::in)))` | signedness transform |
| 1 | `tsldata/primitives/mask/bitwise.tsl:360:85` | `type<generation>(base::unsigned_of(type<generation>(vector::imask)))` | signedness transform |
| 17 | `tsldata/primitives/conversion/repr_change.tsl:1401:61` | `type<generation>(register::generic(ChunkVec))` | generic-register projection |
| 6 | `tsldata/primitives/conversion/repr_change.tsl:1526:105` | `type<generation>(register::generic(HalfVec))` | generic-register projection |
| 26 | `tsldata/primitives/conversion/repr_change.tsl:1331:53` | `type<generation>(register::generic(OutVec))` | generic-register projection |
| 97 | `tsldata/primitives/conversion/cast.tsl:34:47` | `type<generation>(register::generic(ToType))` | generic-register projection |
| 66 | `tsldata/primitives/conversion/repr_change.tsl:541:51` | `type<generation>(register::generic(type<generation>(vector::transform_extension(ToBase))))` | generic-register projection |
| 9 | `tsldata/primitives/bitwise/bit_counts.tsl:97:37` | `type<generation>(select(value<generation>(type::is_same(type<generation>(base::in), f32)), ui32, ui64))` | type select |
| 6 | `tsldata/primitives/conversion/repr_change.tsl:121:37` | `type<generation>(vector::as_extension(ToExtension))` | `vector::as_extension` |
| 7 | `tsldata/primitives/conversion/repr_change.tsl:1513:39` | `type<generation>(vector::as_extension(avx2, ToBase))` | `vector::as_extension` |
| 7 | `tsldata/primitives/load_store/pack_expand.tsl:281:37` | `type<generation>(vector::as_extension(avx2, type<generation>(base::in)))` | `vector::as_extension` |
| 16 | `tsldata/primitives/conversion/repr_change.tsl:1400:39` | `type<generation>(vector::as_extension(sse, ToBase))` | `vector::as_extension` |
| 11 | `tsldata/primitives/load_store/pack_expand.tsl:289:37` | `type<generation>(vector::as_extension(sse, type<generation>(base::in)))` | `vector::as_extension` |
| 39 | `tsldata/primitives/bitwise/bit_counts.tsl:214:52` | `type<generation>(vector::imask)` | context vector member |
| 22 | `tsldata/primitives/comparison/fundamental.tsl:39:30` | `type<generation>(vector::mask)` | context vector member |
| 7 | `tsldata/primitives/load_store/load.tsl:386:26` | `type<generation>(vector::mask_underlying_t)` | context vector member |
| 7 | `tsldata/primitives/bitwise/bit_counts.tsl:71:118` | `type<generation>(vector::offset_base)` | context vector member |
| 22 | `tsldata/primitives/comparison/fundamental.tsl:54:34` | `type<generation>(vector::register)` | context vector member |
| 5 | `tsldata/primitives/comparison/fundamental.tsl:142:32` | `type<generation>(vector::transform(type<generation>(base::unsigned_of(type<generation>(base::in)))))` | vector transform |
| 1 | `tsldata/primitives/load_store/store.tsl:239:34` | `type<generation>(vector::transform(type<generation>(vector::mask_underlying_t)))` | vector transform |
| 2 | `tsldata/primitives/load_store/pack_expand.tsl:72:33` | `type<generation>(vector::transform_extension(IndexBase))` | vector transform |
| 2 | `tsldata/primitives/bitwise/shifts.tsl:1226:40` | `type<generation>(vector::transform_extension(SignedT))` | vector transform |
| 160 | `tsldata/primitives/conversion/cast.tsl:615:37` | `type<generation>(vector::transform_extension(ToBase))` | vector transform |
| 9 | `tsldata/primitives/conversion/cast.tsl:755:37` | `type<generation>(vector::transform_extension(UBase))` | vector transform |
| 1 | `tsldata/primitives/conversion/mask_specific.tsl:274:31` | `type<generation>(vector::transform_extension(UnsignedT))` | vector transform |
| 4 | `tsldata/primitives/conversion/cast.tsl:628:40` | `type<generation>(vector::transform_extension(type<backend>(scalar::si16)))` | vector transform over backend request |
| 3 | `tsldata/primitives/conversion/cast.tsl:665:40` | `type<generation>(vector::transform_extension(type<backend>(scalar::si32)))` | vector transform over backend request |
| 1 | `tsldata/primitives/conversion/mask_specific.tsl:463:34` | `type<generation>(vector::transform_extension(type<backend>(scalar::si64)))` | vector transform over backend request |
| 4 | `tsldata/primitives/conversion/cast.tsl:631:40` | `type<generation>(vector::transform_extension(type<backend>(scalar::ui16)))` | vector transform over backend request |
| 2 | `tsldata/primitives/conversion/cast.tsl:668:40` | `type<generation>(vector::transform_extension(type<backend>(scalar::ui32)))` | vector transform over backend request |
| 5 | `tsldata/primitives/bitwise/shifts.tsl:878:35` | `type<generation>(vector::transform_extension(type<generation>(base::unsigned_of(type<generation>(base::in)))))` | vector transform |

## `type<backend>(...)` Forms

| Count | Representative source | Form | Category |
| ---: | --- | --- | --- |
| 1 | `tsldata/primitives/bitwise/bit_counts.tsl:214:85` | `type<backend>(intrin::vector::imask)` | independent intrinsic type |
| 4 | `tsldata/primitives/conversion/cast.tsl:628:85` | `type<backend>(scalar::si16)` | independent scalar type |
| 6 | `tsldata/primitives/conversion/cast.tsl:665:85` | `type<backend>(scalar::si32)` | independent scalar type |
| 4 | `tsldata/primitives/conversion/mask_specific.tsl:463:79` | `type<backend>(scalar::si64)` | independent scalar type |
| 4 | `tsldata/primitives/conversion/cast.tsl:631:85` | `type<backend>(scalar::ui16)` | independent scalar type |
| 3 | `tsldata/primitives/conversion/cast.tsl:668:85` | `type<backend>(scalar::ui32)` | independent scalar type |
| 14 | `tsldata/primitives/conversion/mask_specific.tsl:224:108` | `type<backend>(scalar::ui64)` | independent scalar type |
| 32 | `tsldata/primitives/load_store/load.tsl:456:57` | `type<backend>(scalar::ui8)` | independent scalar type |
| 62 | `tsldata/primitives/arithmetic/horizontal.tsl:241:13` | `type<backend>(size_t)` | independent size type |
| 49 | `tsldata/primitives/arithmetic/complex.tsl:66:35` | `type<backend>(vector::as_extension(generic))` | backend request over vector type |
| 33 | `tsldata/primitives/arithmetic/complex.tsl:39:48` | `type<backend>(vector::as_extension(scalar))` | backend request over vector type |

## M143 Coverage

M143 lowers every unique observed form above through typed semantic type
values or typed backend type-spelling requests. Backend spellings remain
unrendered. Source strings are retained only on alias bindings and backend
requests as provenance for diagnostics.

There are no deliberately unsupported observed `let<type>`,
`type<generation>`, or `type<backend>` forms after M143. Future corpus changes
that add new type forms must extend this inventory and add focused lowering
tests before primitive-call selector resolution relies on them.
