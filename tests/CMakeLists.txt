# Help CMake find the system GTest on Debian/Ubuntu if not already set
if(NOT DEFINED GTest_DIR AND EXISTS "/usr/lib/x86_64-linux-gnu/cmake/GTest")
    set(GTest_DIR "/usr/lib/x86_64-linux-gnu/cmake/GTest")
endif()
find_package(GTest QUIET)

if(GTest_FOUND)
    add_executable(qf_tests
        test_math.cpp
        test_termstructure.cpp
        test_instruments.cpp
        test_pricingengines.cpp
        test_models.cpp
        test_risk.cpp
        test_market_environment.cpp
        test_models_interfaces.cpp
    )

    target_link_libraries(qf_tests PRIVATE qf GTest::gtest_main)
    target_include_directories(qf_tests PRIVATE ${CMAKE_SOURCE_DIR}/include)

    include(GoogleTest)
    gtest_discover_tests(qf_tests)
else()
    message(WARNING "GoogleTest not found — tests will not be built. Install with: sudo apt install libgtest-dev")
endif()
