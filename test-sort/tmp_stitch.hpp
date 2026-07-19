#pragma once
#include <immintrin.h>
#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>

template <typename T> struct algo;
template <typename T> struct algo_optimized;
template <typename T> struct algo_optimized2;
template <typename T> struct algo_hybrid;
template <typename T,unsigned Substitutions> struct algo_substitution;
template <typename T,unsigned Substitutions> struct algo_substitution_v1;

template <> struct algo<std::uint64_t> {
    static constexpr std::size_t lane_count = 8;
    using MaskT = __mmask8;
    static inline __m512i shift_indices_lanes(std::size_t offset) {
        alignas(64) static constexpr auto lut = [] {
            std::array<std::uint64_t, lane_count * lane_count> r{};
            for (std::size_t o=0;o<lane_count;++o) { std::uint64_t x=0; for(std::size_t i=o;i<lane_count;++i) r[o*lane_count+i]=x++; }
            return r;
        }();
        return _mm512_load_si512(lut.data()+lane_count*offset);
    }
    static inline __m512i compact_index_lanes(MaskT mask) {
        alignas(64) static constexpr auto lut=[] {
            std::array<std::uint64_t,(1u<<lane_count)*lane_count> r{};
            for(std::size_t m=0;m<(1u<<lane_count);++m){std::size_t out=0;for(std::size_t i=0;i<lane_count;++i)if(m&(std::size_t{1}<<i))r[m*lane_count+out++]=i;}
            return r;
        }();
        return _mm512_load_si512(lut.data()+static_cast<std::size_t>(mask)*lane_count);
    }
    static inline __m512i compactify_and_move_in_place(__m512i d,MaskT m){return _mm512_permutexvar_epi64(compact_index_lanes(m),d);}
    static inline __m512i compactify_and_concat(__m512i s,MaskT m,__m512i d,MaskT p,std::size_t o){auto i=_mm512_permutexvar_epi64(shift_indices_lanes(o),compact_index_lanes(m));return _mm512_mask_permutexvar_epi64(s,p,i,d);}
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){MaskT cp=static_cast<MaskT>(~0u)<<lc;MaskT rp=cp<<cc;auto r=compactify_and_move_in_place(ld,lm);r=compactify_and_concat(r,cm,cd,cp,lc);return compactify_and_concat(r,rm,rd,rp,lc+cc);}
};

template <> struct algo<std::uint32_t> {
    static constexpr std::size_t lane_count=16,lut_lane_count=8;
    using DataT=std::uint32_t; using MaskT=__mmask16;
    static inline __m512i shift_indices_lanes(std::size_t offset){
        alignas(64) static constexpr auto lut=[] {std::array<DataT,lane_count*lane_count> r{};for(std::size_t o=0;o<lane_count;++o){DataT x=0;for(std::size_t i=o;i<lane_count;++i)r[o*lane_count+i]=x++;}return r;}();
        return _mm512_load_si512(lut.data()+lane_count*offset);
    }
    static inline __m512i compact_index_lanes(MaskT mask){
        alignas(64) static constexpr auto lut=[] {std::array<DataT,(1u<<lut_lane_count)*lut_lane_count> r{};for(unsigned m=0;m<(1u<<lut_lane_count);++m){std::size_t out=0,lane=0;auto end=std::bit_width(m);for(;lane<end;++lane)if(m&(1u<<lane))r[m*lut_lane_count+out++]=lane;for(;lane<lut_lane_count;++lane)r[m*lut_lane_count+out++]=lane;}return r;}();
        auto low=static_cast<MaskT>(mask&0xffu),high=static_cast<MaskT>((mask>>8)&0xffu);auto count=std::popcount(static_cast<unsigned>(low));
        auto li=_mm256_load_si256(reinterpret_cast<__m256i const*>(lut.data()+static_cast<std::size_t>(low)*8));
        auto hi=_mm256_load_si256(reinterpret_cast<__m256i const*>(lut.data()+static_cast<std::size_t>(high)*8));
        alignas(32) static constexpr std::array<DataT,8> offsets={8,8,8,8,8,8,8,8};
        hi=_mm256_add_epi32(hi,_mm256_load_si256(reinterpret_cast<__m256i const*>(offsets.data())));
        auto hi512=_mm512_inserti64x4(_mm512_castsi256_si512(hi),hi,1);
        return _mm512_mask_permutexvar_epi32(_mm512_castsi256_si512(li),static_cast<MaskT>(0xffffu<<count),shift_indices_lanes(count),hi512);
    }
    static inline __m512i compactify_and_move_in_place(__m512i d,MaskT m){return _mm512_permutexvar_epi32(compact_index_lanes(m),d);}
    static inline __m512i compactify_and_concat(__m512i s,MaskT m,__m512i d,MaskT p,std::size_t o){auto i=_mm512_permutexvar_epi32(shift_indices_lanes(o),compact_index_lanes(m));return _mm512_mask_permutexvar_epi32(s,p,i,d);}
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){MaskT cp=static_cast<MaskT>(~0u)<<lc;MaskT rp=cp<<cc;auto r=compactify_and_move_in_place(ld,lm);r=compactify_and_concat(r,cm,cd,cp,lc);return compactify_and_concat(r,rm,rd,rp,lc+cc);}
};

template <> struct algo_optimized<std::uint32_t> {
    static constexpr std::size_t lane_count=16,lut_lane_count=8;
    using DataT=std::uint32_t; using MaskT=__mmask16;
    static inline __m512i shift_indices_lanes(std::size_t offset){
        alignas(64) static constexpr auto lut=[] {std::array<DataT,lane_count*lane_count> r{};for(std::size_t o=0;o<lane_count;++o){DataT x=0;for(std::size_t i=o;i<lane_count;++i)r[o*lane_count+i]=x++;}return r;}();
        return _mm512_load_si512(lut.data()+lane_count*offset);
    }
    static inline __m512i compact_index_lanes(MaskT mask){
        struct CompactTables {std::array<DataT,(1u<<lut_lane_count)*lut_lane_count> low{};std::array<DataT,(1u<<lut_lane_count)*lut_lane_count> high{};};
        alignas(64) static constexpr auto lut=[] {CompactTables r{};for(unsigned m=0;m<(1u<<lut_lane_count);++m){std::size_t out=0,lane=0;auto end=std::bit_width(m);for(;lane<end;++lane)if(m&(1u<<lane)){r.low[m*8+out]=lane;r.high[m*8+out++]=lane+8;}for(;lane<8;++lane){r.low[m*8+out]=lane;r.high[m*8+out++]=lane+8;}}return r;}();
        alignas(64) static constexpr auto stitch_lut=[] {std::array<DataT,(lut_lane_count+1)*lane_count> r{};for(std::size_t count=0;count<=8;++count)for(std::size_t lane=0;lane<16;++lane)r[count*16+lane]=lane<count?lane:8+(lane-count)%8;return r;}();
        auto low=static_cast<MaskT>(mask&0xffu),high=static_cast<MaskT>((mask>>8)&0xffu);auto count=std::popcount(static_cast<unsigned>(low));
        auto li=_mm256_load_si256(reinterpret_cast<__m256i const*>(lut.low.data()+static_cast<std::size_t>(low)*8));auto hi=_mm256_load_si256(reinterpret_cast<__m256i const*>(lut.high.data()+static_cast<std::size_t>(high)*8));
        auto combined=_mm512_inserti64x4(_mm512_castsi256_si512(li),hi,1);auto stitch=_mm512_load_si512(stitch_lut.data()+count*16);return _mm512_permutexvar_epi32(stitch,combined);
    }
    static inline __m512i compactify_and_move_in_place(__m512i d,MaskT m){return _mm512_permutexvar_epi32(compact_index_lanes(m),d);}
    static inline __m512i compactify_and_concat(__m512i s,MaskT m,__m512i d,MaskT p,std::size_t o){auto i=_mm512_permutexvar_epi32(shift_indices_lanes(o),compact_index_lanes(m));return _mm512_mask_permutexvar_epi32(s,p,i,d);}
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){MaskT cp=static_cast<MaskT>(~0u)<<lc;MaskT rp=cp<<cc;auto r=compactify_and_move_in_place(ld,lm);r=compactify_and_concat(r,cm,cd,cp,lc);return compactify_and_concat(r,rm,rd,rp,lc+cc);}
};

template <> struct algo_optimized2<std::uint32_t> {
    static constexpr std::size_t lane_count=16,lut_lane_count=8;
    using DataT=std::uint32_t; using MaskT=__mmask16;
    static inline __m512i shift_indices_lanes(std::size_t offset){
        alignas(64) static constexpr auto lut=[] {std::array<DataT,lane_count*lane_count> r{};for(std::size_t o=0;o<lane_count;++o){DataT x=0;for(std::size_t i=o;i<lane_count;++i)r[o*lane_count+i]=x++;}return r;}();
        return _mm512_load_si512(lut.data()+lane_count*offset);
    }
    static inline __m512i compact_index_lanes(MaskT mask,std::size_t offset=0){
        struct CompactTables {
            std::array<DataT,(1u<<lut_lane_count)*lut_lane_count> low{};
            std::array<DataT,(1u<<lut_lane_count)*lut_lane_count> high{};
        };
        alignas(64) static constexpr auto lut=[] {
            CompactTables r{};
            for(unsigned m=0;m<(1u<<lut_lane_count);++m){
                std::size_t out=0,lane=0;auto end=std::bit_width(m);
                for(;lane<end;++lane)if(m&(1u<<lane)){
                    r.low[m*lut_lane_count+out]=lane;
                    r.high[m*lut_lane_count+out++]=lane+lut_lane_count;
                }
                for(;lane<lut_lane_count;++lane){
                    r.low[m*lut_lane_count+out]=lane;
                    r.high[m*lut_lane_count+out++]=lane+lut_lane_count;
                }
            }
            return r;
        }();
        alignas(64) static constexpr auto stitch_lut=[] {
            std::array<DataT,lane_count*(lut_lane_count+1)*lane_count> r{};
            for(std::size_t offset=0;offset<lane_count;++offset){
                for(std::size_t count=0;count<=lut_lane_count;++count){
                    auto const base=(offset*(lut_lane_count+1)+count)*lane_count;
                    for(std::size_t lane=0;lane<lane_count;++lane){
                        if(lane<offset){
                            r[base+lane]=0;
                            continue;
                        }
                        auto const compact_lane=lane-offset;
                        r[base+lane]=compact_lane<count
                            ? static_cast<DataT>(compact_lane)
                            : static_cast<DataT>(lut_lane_count+(compact_lane-count)%lut_lane_count);
                    }
                }
            }
            return r;
        }();
        auto low=static_cast<MaskT>(mask&0xffu),high=static_cast<MaskT>((mask>>8)&0xffu);auto count=std::popcount(static_cast<unsigned>(low));
        auto li=_mm256_load_si256(reinterpret_cast<__m256i const*>(lut.low.data()+static_cast<std::size_t>(low)*8));
        auto hi=_mm256_load_si256(reinterpret_cast<__m256i const*>(lut.high.data()+static_cast<std::size_t>(high)*8));
        auto combined=_mm512_inserti64x4(_mm512_castsi256_si512(li),hi,1);
        auto stitch=_mm512_load_si512(
            stitch_lut.data()+(offset*(lut_lane_count+1)+count)*lane_count
        );
        return _mm512_permutexvar_epi32(stitch,combined);
    }
    static inline __m512i compactify_and_move_in_place(__m512i d,MaskT m){return _mm512_permutexvar_epi32(compact_index_lanes(m),d);}
    static inline __m512i compactify_and_concat(__m512i s,MaskT m,__m512i d,MaskT p,std::size_t o){return _mm512_mask_permutexvar_epi32(s,p,compact_index_lanes(m,o),d);}
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){MaskT cp=static_cast<MaskT>(~0u)<<lc;MaskT rp=cp<<cc;auto r=compactify_and_move_in_place(ld,lm);r=compactify_and_concat(r,cm,cd,cp,lc);return compactify_and_concat(r,rm,rd,rp,lc+cc);}
};

template <> struct algo_hybrid<std::uint32_t> : algo_optimized2<std::uint32_t> {
    using Base=algo_optimized2<std::uint32_t>;
    using MaskT=Base::MaskT;
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){
        MaskT cp=static_cast<MaskT>(~0u)<<lc;
        MaskT rp=cp<<cc;
        auto result=_mm512_maskz_compress_epi32(lm,ld);
        result=Base::compactify_and_concat(result,cm,cd,cp,lc);
        return Base::compactify_and_concat(result,rm,rd,rp,lc+cc);
    }
};

template <unsigned Substitutions>
struct algo_substitution<std::uint32_t,Substitutions> : algo_optimized2<std::uint32_t> {
    using Base=algo_optimized2<std::uint32_t>;
    using MaskT=Base::MaskT;
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){
        static_assert(Substitutions<8);
        MaskT cp=static_cast<MaskT>(~0u)<<lc;
        MaskT rp=cp<<cc;
        __m512i result;
        if constexpr(Substitutions&1) result=_mm512_maskz_compress_epi32(lm,ld);
        else result=Base::compactify_and_move_in_place(ld,lm);
        if constexpr(Substitutions&2){
            auto center=_mm512_maskz_compress_epi32(cm,cd);
            result=_mm512_mask_expand_epi32(result,cp,center);
        }else result=Base::compactify_and_concat(result,cm,cd,cp,lc);
        if constexpr(Substitutions&4){
            auto right=_mm512_maskz_compress_epi32(rm,rd);
            return _mm512_mask_expand_epi32(result,rp,right);
        }else return Base::compactify_and_concat(result,rm,rd,rp,lc+cc);
    }
};

template <unsigned Substitutions>
struct algo_substitution_v1<std::uint32_t,Substitutions> : algo_optimized<std::uint32_t> {
    using Base=algo_optimized<std::uint32_t>;
    using MaskT=Base::MaskT;
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){
        static_assert(Substitutions<8);
        MaskT cp=static_cast<MaskT>(~0u)<<lc;
        MaskT rp=cp<<cc;
        __m512i result;
        if constexpr(Substitutions&1) result=_mm512_maskz_compress_epi32(lm,ld);
        else result=Base::compactify_and_move_in_place(ld,lm);
        if constexpr(Substitutions&2){
            auto center=_mm512_maskz_compress_epi32(cm,cd);
            result=_mm512_mask_expand_epi32(result,cp,center);
        }else result=Base::compactify_and_concat(result,cm,cd,cp,lc);
        if constexpr(Substitutions&4){
            auto right=_mm512_maskz_compress_epi32(rm,rd);
            return _mm512_mask_expand_epi32(result,rp,right);
        }else return Base::compactify_and_concat(result,rm,rd,rp,lc+cc);
    }
};

template <typename T> struct gold_standard_optimized;

template <> struct gold_standard_optimized<std::uint64_t> {
    using MaskT=__mmask8;
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){
        auto result=_mm512_maskz_compress_epi64(lm,ld);
        auto center=_mm512_maskz_compress_epi64(cm,cd);
        auto right=_mm512_maskz_compress_epi64(rm,rd);
        result=_mm512_mask_expand_epi64(result,static_cast<MaskT>(~0u)<<lc,center);
        return _mm512_mask_expand_epi64(result,static_cast<MaskT>(~0u)<<(lc+cc),right);
    }
};

template <> struct gold_standard_optimized<std::uint32_t> {
    using MaskT=__mmask16;
    static inline __m512i concat_compact_3way(MaskT lm,__m512i ld,int lc,MaskT cm,__m512i cd,int cc,MaskT rm,__m512i rd){
        auto result=_mm512_maskz_compress_epi32(lm,ld);
        auto center=_mm512_maskz_compress_epi32(cm,cd);
        auto right=_mm512_maskz_compress_epi32(rm,rd);
        result=_mm512_mask_expand_epi32(result,static_cast<MaskT>(~0u)<<lc,center);
        return _mm512_mask_expand_epi32(result,static_cast<MaskT>(~0u)<<(lc+cc),right);
    }
};
