//! Native CPU identity shared by Rust benchmark production and policy consumption.

pub fn precise_x86_cpu_id(value: &str) -> bool {
    let fields = value.split(':').collect::<Vec<_>>();
    fields.len() == 5
        && fields[0] == "x86"
        && fields[1].len() == 12
        && fields[2..].iter().all(|field| field.parse::<u32>().is_ok())
}

pub fn cpu_id() -> String {
    #[cfg(target_arch = "x86_64")]
    {
        let vendor_leaf = std::arch::x86_64::__cpuid(0);
        let identity = std::arch::x86_64::__cpuid(1);
        let mut vendor = Vec::with_capacity(12);
        vendor.extend_from_slice(&vendor_leaf.ebx.to_le_bytes());
        vendor.extend_from_slice(&vendor_leaf.edx.to_le_bytes());
        vendor.extend_from_slice(&vendor_leaf.ecx.to_le_bytes());
        let vendor = String::from_utf8_lossy(&vendor);
        let stepping = identity.eax & 0xf;
        let base_model = (identity.eax >> 4) & 0xf;
        let base_family = (identity.eax >> 8) & 0xf;
        let model = if base_family == 0x6 || base_family == 0xf {
            base_model + (((identity.eax >> 16) & 0xf) << 4)
        } else {
            base_model
        };
        let family = if base_family == 0xf {
            base_family + ((identity.eax >> 20) & 0xff)
        } else {
            base_family
        };
        return format!("x86:{vendor}:{family}:{model}:{stepping}");
    }
    #[cfg(target_arch = "aarch64")]
    {
        return "aarch64:insufficient-identity".to_string();
    }
    #[allow(unreachable_code)]
    "unknown-architecture".to_string()
}
