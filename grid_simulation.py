import pandapower as pp

def create_grid():
    net = pp.create_empty_network()

    # Buses
    bus1 = pp.create_bus(net, vn_kv=110)
    bus2 = pp.create_bus(net, vn_kv=20)
    bus3 = pp.create_bus(net, vn_kv=20)

    # External grid
    pp.create_ext_grid(net, bus=bus1, vm_pu=1.0)

    # Transformer
    pp.create_transformer_from_parameters(
        net,
        hv_bus=bus1,
        lv_bus=bus2,
        sn_mva=200,
        vn_hv_kv=110,
        vn_lv_kv=20,
        vk_percent=10,
        vkr_percent=0.5,
        pfe_kw=0,
        i0_percent=0
    )

    # Line
    pp.create_line_from_parameters(
        net,
        from_bus=bus2,
        to_bus=bus3,
        length_km=5,
        r_ohm_per_km=0.1,
        x_ohm_per_km=0.2,
        c_nf_per_km=10,
        max_i_ka=4.0
    )

    # Loads
    pp.create_load(net, bus=bus2, p_mw=30)
    dc_load = pp.create_load(net, bus=bus3, p_mw=20)

    return net, dc_load


def run_simulation(net):
    pp.runpp(net, numba=False)

    return {
        "max_line_loading": float(net.res_line.loading_percent.max()),
        "min_voltage": float(net.res_bus.vm_pu.min()),
        "total_load": float(net.load.p_mw.sum())
    }


def increase_data_center_demand(net, dc_load, value):
    net.load.at[dc_load, "p_mw"] = value