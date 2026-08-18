#include <iostream>

#include "pipcost/measurement.hpp"

int main() {
    if (!pipcost::run_correctness_suite()) {
        std::cerr << "PIPCost kernel correctness suite failed\n";
        return 1;
    }
    return 0;
}
