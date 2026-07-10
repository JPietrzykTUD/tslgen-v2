cmake -S . -B build -DCMAKE_CXX_COMPILER=/usr/bin/c++ -DTSL_PROFILE=auto
cmake --build build --config Debug --target 


# ./dev.sh generate --backends cpp --output-root ./tslctmp/test-sort-generated
# cmake -S test-sort -B test-sort/build-local \
#   -DCMAKE_CXX_COMPILER=/usr/bin/c++ \
#   -DTSL_PROFILE=auto \
#   -DTSL_LOCAL_SOURCE_DIR=/workspaces/tslgen-v99/tslctmp/test-sort-generated