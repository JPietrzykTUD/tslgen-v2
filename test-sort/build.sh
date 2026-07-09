cmake -S . -B build -DCMAKE_CXX_COMPILER=/usr/bin/c++ -DTSL_PROFILE=auto
cmake --build build --config Debug --target all