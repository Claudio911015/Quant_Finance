find_package(GTest QUIET)

if(GTest_FOUND)
    add_executable(qf_tests
        test_math.cpp
        test_termstructure.cpp
        test_instruments.cpp
        test_pricingengines.cpp
        test_models.cpp
        test_risk.cpp
    )

    target_link_libraries(qf_tests PRIVATE qf GTest::gtest_main)
    target_include_directories(qf_tests PRIVATE ${CMAKE_SOURCE_DIR}/include)

    include(GoogleTest)
    gtest_discover_tests(qf_tests)
else()
    message(WARNING "GoogleTest not found — tests will not be built. Install with: sudo apt install libgtest-dev")
endif()
