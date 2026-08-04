#include <cstdlib>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>

#include "pipcost/data.hpp"
#include "pipcost/measurement.hpp"

namespace {

std::string json_escape(const std::string& value) {
    std::string output;
    for (const char c : value) {
        switch (c) {
            case '"':
                output += "\\\"";
                break;
            case '\\':
                output += "\\\\";
                break;
            case '\n':
                output += "\\n";
                break;
            case '\r':
                output += "\\r";
                break;
            case '\t':
                output += "\\t";
                break;
            default:
                output += c;
        }
    }
    return output;
}

std::map<std::string, std::string> arguments(int argc, char** argv) {
    std::map<std::string, std::string> result;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        if (key == "--list-plans" || key == "--self-test") {
            result[key] = "true";
            continue;
        }
        if (key == "--format") {
            if (i + 1 >= argc) {
                throw std::invalid_argument("--format requires a value");
            }
            result[key] = argv[++i];
            continue;
        }
        if (key.rfind("--", 0) != 0 || i + 1 >= argc) {
            throw std::invalid_argument("expected --key value arguments");
        }
        result[key] = argv[++i];
    }
    return result;
}

const std::string& require(
    const std::map<std::string, std::string>& values,
    const std::string& key) {
    const auto found = values.find(key);
    if (found == values.end()) {
        throw std::invalid_argument("missing required argument " + key);
    }
    return found->second;
}

void list_plans() {
    std::cout << "{\"plans\":[";
    bool first = true;
    for (const auto& plan : pipcost::plan_registry()) {
        if (!first) {
            std::cout << ",";
        }
        first = false;
        std::cout
            << "{\"mask_layout\":"
            << (plan.mask_layout.empty()
                    ? "null"
                    : "\"" + json_escape(std::string(plan.mask_layout)) + "\"")
            << ",\"implementation\":\""
            << json_escape(std::string(plan.implementation)) << "\""
            << ",\"materialized\":" << (plan.materialized ? "true" : "false")
            << ",\"plan_id\":\"" << json_escape(std::string(plan.plan_id)) << "\""
            << ",\"position_width\":"
            << (plan.position_width == 0
                    ? "null"
                    : std::to_string(plan.position_width))
            << ",\"processing_mode\":\""
            << json_escape(std::string(plan.processing_mode)) << "\""
            << ",\"representation\":\""
            << json_escape(std::string(plan.representation)) << "\""
            << ",\"scope\":\"" << json_escape(std::string(plan.scope)) << "\""
            << ",\"simd_lanes\":" << plan.simd_lanes
            << ",\"skip_reason\":"
            << (plan.skip_reason.empty()
                    ? "null"
                    : "\"" + json_escape(std::string(plan.skip_reason)) + "\"")
            << ",\"supported\":" << (plan.supported ? "true" : "false")
            << ",\"vectorization\":\""
            << json_escape(std::string(plan.vectorization)) << "\""
            << "}";
    }
    std::cout << "]}\n";
}

int run_plan(const std::map<std::string, std::string>& args) {
    const auto* plan = pipcost::find_plan(require(args, "--plan"));
    if (plan == nullptr) {
        throw std::invalid_argument("unknown plan");
    }
    if (!plan->supported) {
        std::cout
            << "{\"plan_id\":\"" << json_escape(std::string(plan->plan_id))
            << "\",\"reason\":\""
            << json_escape(std::string(plan->skip_reason))
            << "\",\"status\":\"unsupported\"}\n";
        return 2;
    }

    const pipcost::DataSpec spec{
        static_cast<std::size_t>(std::stoull(require(args, "--rows"))),
        std::stod(require(args, "--first-selectivity")),
        std::stod(require(args, "--conditional-selectivity")),
        require(args, "--pattern"),
        std::stoull(require(args, "--seed")),
    };
    const auto data = pipcost::generate_data(spec);
    const auto expected = pipcost::scalar_reference(data);
    const pipcost::QueryView query{
        data.a.data(),
        data.b.data(),
        data.c.data(),
        data.a.size(),
        static_cast<std::size_t>(std::stoull(require(args, "--batch-rows"))),
        data.p1,
        data.p2,
    };
    pipcost::Scratch scratch(data.a.size());
    const auto checked = plan->function(query, scratch);
    if (checked.sum != expected || !scratch.canaries_intact()) {
        std::cout
            << "{\"actual\":" << checked.sum
            << ",\"expected\":" << expected
            << ",\"plan_id\":\"" << json_escape(std::string(plan->plan_id))
            << "\",\"status\":\"incorrect\"}\n";
        return 3;
    }

    const auto measured = pipcost::measure_plan(
        *plan,
        query,
        scratch,
        static_cast<std::size_t>(std::stoull(require(args, "--warmups"))),
        static_cast<std::size_t>(
            std::stoull(require(args, "--inner-iterations"))));
    if (!scratch.canaries_intact()) {
        throw std::runtime_error("scratch canary was overwritten during timing");
    }
    const double observed_first = spec.rows == 0
        ? 0.0
        : static_cast<double>(data.first_matches) /
            static_cast<double>(spec.rows);
    const double observed_combined = spec.rows == 0
        ? 0.0
        : static_cast<double>(data.combined_matches) /
            static_cast<double>(spec.rows);
    const double observed_conditional = data.first_matches == 0
        ? 0.0
        : static_cast<double>(data.combined_matches) /
            static_cast<double>(data.first_matches);

    std::cout << std::setprecision(17)
              << "{\"checksum\":" << measured.checksum
              << ",\"data_digest\":\"" << std::hex << data.digest << std::dec << "\""
              << ",\"elapsed_ns\":" << measured.elapsed_ns
              << ",\"first_matches\":" << data.first_matches
              << ",\"inner_iterations\":"
              << require(args, "--inner-iterations")
              << ",\"observed_combined_selectivity\":"
              << observed_combined
              << ",\"observed_conditional_selectivity\":"
              << observed_conditional
              << ",\"observed_first_selectivity\":" << observed_first
              << ",\"plan_id\":\"" << json_escape(std::string(plan->plan_id)) << "\""
              << ",\"produced\":" << measured.last_result.produced
              << ",\"reference_sum\":" << expected
              << ",\"rows\":" << spec.rows
              << ",\"status\":\"ok\""
              << ",\"sum\":" << measured.last_result.sum
              << "}\n";
    return 0;
}

void usage() {
    std::cerr
        << "usage: pipcost-bench --list-plans --format json\n"
        << "       pipcost-bench --self-test\n"
        << "       pipcost-bench --plan ID --rows N --batch-rows N "
           "--first-selectivity F --conditional-selectivity F "
           "--pattern random|clustered --seed N --warmups N "
           "--inner-iterations N\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto args = arguments(argc, argv);
        if (args.count("--list-plans") != 0) {
            if (args.count("--format") != 0 && args.at("--format") != "json") {
                throw std::invalid_argument("only --format json is supported");
            }
            list_plans();
            return 0;
        }
        if (args.count("--self-test") != 0) {
            const bool ok = pipcost::run_correctness_suite();
            std::cout << "{\"status\":\"" << (ok ? "ok" : "failed") << "\"}\n";
            return ok ? 0 : 1;
        }
        if (args.count("--plan") != 0) {
            return run_plan(args);
        }
        usage();
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "pipcost-bench: " << error.what() << "\n";
        return 2;
    }
}
