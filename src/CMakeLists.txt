add_library(qf
    math/interpolation.cpp
    math/rootfinding.cpp
    math/integration.cpp
    termstructure/yieldcurve.cpp
    instruments/bond.cpp
    instruments/swap.cpp
    instruments/option.cpp
    pricingengines/blackscholes.cpp
    pricingengines/binomialtree.cpp
    pricingengines/montecarlo.cpp
    pricingengines/finite_difference.cpp
    models/vasicek.cpp
    models/hullwhite.cpp
    risk/greeks.cpp
    risk/var.cpp
)

target_include_directories(qf
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_compile_features(qf PUBLIC cxx_std_17)
