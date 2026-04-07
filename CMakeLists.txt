cmake_minimum_required(VERSION 3.15)

project(QuantFinance
    VERSION 0.1.0
    DESCRIPTION "C++ quantitative finance library"
    LANGUAGES CXX
)

# ── C++ standard ──────────────────────────────────────────────────────────────
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Build options ─────────────────────────────────────────────────────────────
option(QF_BUILD_TESTS    "Build unit tests"  ON)
option(QF_BUILD_EXAMPLES "Build examples"    ON)

# ── Compiler warnings ─────────────────────────────────────────────────────────
if(MSVC)
    add_compile_options(/W4)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ── Library ───────────────────────────────────────────────────────────────────
add_subdirectory(src)

# ── Tests ─────────────────────────────────────────────────────────────────────
if(QF_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# ── Documentation ─────────────────────────────────────────────────────────────
option(QF_BUILD_DOCS "Build API docs with Doxygen" ON)
if(QF_BUILD_DOCS)
    find_package(Doxygen QUIET)
    if(DOXYGEN_FOUND)
        set(DOXYGEN_IN ${CMAKE_SOURCE_DIR}/Doxyfile)
        set(DOXYGEN_OUT ${CMAKE_BINARY_DIR}/Doxyfile)
        add_custom_command(
            OUTPUT ${DOXYGEN_OUT}
            COMMAND ${CMAKE_COMMAND} -E copy_if_different ${DOXYGEN_IN} ${DOXYGEN_OUT}
            DEPENDS ${DOXYGEN_IN}
            COMMENT "Copy Doxyfile"
        )

        add_custom_target(doxygen ALL
            DEPENDS ${DOXYGEN_OUT}
            COMMAND ${DOXYGEN_EXECUTABLE} ${DOXYGEN_OUT}
            WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
            COMMENT "Generating API documentation with Doxygen"
            VERBATIM
        )

        set_target_properties(doxygen PROPERTIES FOLDER "documentation")
    else()
        message(WARNING "Doxygen not found. Docs target won't be built.")
    endif()
endif()

# ── Examples ──────────────────────────────────────────────────────────────────
if(QF_BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

# ── Web UI (Python) ──────────────────────────────────────────────────────────
option(QF_BUILD_WEB "Build/run the Python web UI" ON)
find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_FOUND)
    if(QF_BUILD_WEB)
        add_custom_target(run_web_ui
            COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/python_web/app.py
            WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
            COMMENT "Run Python Flask UI (localhost:5001)"
            USES_TERMINAL
        )
    endif()

    add_custom_target(pytests
        COMMAND ${Python3_EXECUTABLE} -m unittest discover -s ${CMAKE_SOURCE_DIR}/tests -p "test_*.py"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        COMMENT "Run Python unit tests"
    )
else()
    message(WARNING "Python3 not found. Web UI target and pytests target will not be available.")
endif()
