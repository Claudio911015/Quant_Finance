add_library(qf
    core/market_environment.cpp
    math/interpolation.cpp
    math/rootfinding.cpp
    math/integration.cpp
    math/statistics.cpp
    math/daycount.cpp
    math/optimization.cpp
    termstructure/yieldcurve.cpp
    termstructure/volsurface.cpp
    termstructure/bootstrap.cpp
    instruments/instrument.cpp
    instruments/iunderlying.cpp
    instruments/bond.cpp
    instruments/swap.cpp
    instruments/option.cpp
    instruments/capfloor.cpp
    instruments/swaption.cpp
    pricingengines/engine_factory.cpp
    pricingengines/blackscholes.cpp
    pricingengines/binomialtree.cpp
    pricingengines/montecarlo.cpp
    pricingengines/finite_difference.cpp
    pricingengines/heston.cpp
    models/vasicek.cpp
    models/hullwhite.cpp
    models/heston_model.cpp
    models/heston_calibrator.cpp
    models/bs_model.cpp
    risk/greeks.cpp
    risk/var.cpp
    risk/scenario.cpp
    xva/credit_curve.cpp
    xva/netting_set.cpp
    xva/cva_calculator.cpp
)

target_include_directories(qf
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_compile_features(qf PUBLIC cxx_std_17)

# Optional Python bindings via pybind11
find_package(pybind11 QUIET)
if(pybind11_FOUND)
    pybind11_add_module(qfpy
        python_bindings/qfpy.cpp
    )
    target_link_libraries(qfpy PRIVATE qf)
    target_include_directories(qfpy PRIVATE ${CMAKE_SOURCE_DIR}/include)
    set_target_properties(qfpy PROPERTIES PREFIX "")
else()
    message(WARNING "pybind11 not found. Python bindings will not be built.")
endif()

if(pybind11_FOUND)
    pybind11_add_module(qfxva
        python_bindings/xva_bindings.cpp
    )
    target_link_libraries(qfxva PRIVATE qf)
    target_include_directories(qfxva PRIVATE ${CMAKE_SOURCE_DIR}/include)
    set_target_properties(qfxva PROPERTIES PREFIX "")
endif()
