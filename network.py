import torch
from flow_template import ImageFlow
from flow_dequantization import Dequantization, VariationalDequantization
from flow_models import CouplingLayer, SqueezeFlow, SplitFlow
from nn_layers import GatedConvNet, GatedLinearNet
from tools import create_checkerboard_mask, create_channel_mask


def get_flow_layers(size, c, vardeq=True, num_layers=8, linear=False, partial_conv=False):
    flow_layers = []

    # Dequantization
    if vardeq:
        vardeq_layers = [CouplingLayer(network=GatedConvNet(c_in=2 * c, c_out=2 * c, c_hidden=16, partial_conv=partial_conv),
                                       mask=create_checkerboard_mask(h=size, w=size, invert=(i % 2 == 1)),
                                       c_in=1 * c) for i in range(4)]
        flow_layers += [VariationalDequantization(var_flows=vardeq_layers)]
    else:
        flow_layers += [Dequantization()]

    # Main Flow
    for i in range(num_layers):
        if not linear:
            flow_layers += [CouplingLayer(network=GatedConvNet(c_in=1*c, c_hidden=32, partial_conv=partial_conv),
                                          mask=create_checkerboard_mask(h=size, w=size, invert=(i % 2 == 1)),
                                          c_in=1*c)]
        else:
            num_features = c * size * size
            flow_layers += [CouplingLayer(network=GatedLinearNet(in_features=num_features),
                                          mask=create_checkerboard_mask(h=size, w=size,
                                                                        invert=(i % 2 == 1)),
                                          c_in=1*c)]

    return flow_layers


def create_simple_flow(config):
    """
    Dequantization + 8 * CouplingLayer(GatedConvNet)
    """
    flow_layers = get_flow_layers(config.size, config.c, vardeq=False, num_layers=8, linear=False, partial_conv=False)
    flow_model = ImageFlow(flow_layers, config=config)
    sample_shape_factor = torch.tensor([1, 1, 1, 1])
    return flow_model, sample_shape_factor


def create_vardeq_flow(config):
    """
    Variational Dequantization + 8 * CouplingLayer(GatedConvNet)
    """
    flow_layers = get_flow_layers(config.size, config.c, vardeq=True, num_layers=8, linear=False, partial_conv=False)

    flow_model = ImageFlow(flow_layers, config=config)
    sample_shape_factor = torch.tensor([1, 1, 1, 1])
    return flow_model, sample_shape_factor


def create_long_flow(config):
    """
    Variational Dequantization + 15 * CouplingLayer(GatedConvNet)
    """
    flow_layers = get_flow_layers(config.size, config.c, vardeq=True, num_layers=15, linear=False, partial_conv=False)

    flow_model = ImageFlow(flow_layers, config=config)
    sample_shape_factor = torch.tensor([1, 1, 1, 1])
    return flow_model, sample_shape_factor


def create_linear_flow(config):
    """
    Variational Dequantization + 8 * CouplingLayer(GatedLinearNet)
    """
    flow_layers = get_flow_layers(config.size, config.c, vardeq=True, num_layers=8, linear=True, partial_conv=False)

    flow_model = ImageFlow(flow_layers, config=config)
    sample_shape_factor = torch.tensor([1, 1, 1, 1])
    return flow_model, sample_shape_factor


def create_partial_conv_flow(config):
    """
    Variational Dequantization + 8 * CouplingLayer(GatedLinearNet)
    """
    flow_layers = get_flow_layers(config.size, config.c, vardeq=True, num_layers=8, linear=False, partial_conv=True)

    flow_model = ImageFlow(flow_layers, config=config)
    sample_shape_factor = torch.tensor([1, 1, 1, 1])
    return flow_model, sample_shape_factor


def create_multiscale_flow(config):
    squeeze_twice = True if (config.size % 4 == 0) and (config.size >= 20) else False

    flow_layers = []

    # Vardeq, 2 Coupling
    vardeq_layers = [CouplingLayer(network=GatedConvNet(c_in=2*config.c, c_out=2*config.c, c_hidden=16),
                                   mask=create_checkerboard_mask(h=config.size, w=config.size, invert=(i % 2 == 1)),
                                   c_in=1*config.c) for i in range(4)]
    flow_layers += [VariationalDequantization(vardeq_layers)]

    flow_layers += [CouplingLayer(network=GatedConvNet(c_in=1*config.c, c_hidden=32),
                                  mask=create_checkerboard_mask(h=config.size, w=config.size, invert=(i % 2 == 1)),
                                  c_in=1*config.c) for i in range(2)]

    # Squeeze, 2 Coupling
    flow_layers += [SqueezeFlow()]
    for i in range(2):
        flow_layers += [CouplingLayer(network=GatedConvNet(c_in=4*config.c, c_hidden=48),
                                      mask=create_channel_mask(c_in=4*config.c, invert=(i % 2 == 1)),
                                      c_in=4*config.c)]

    # Split (,Squeeze?), 4 Coupling
    flow_layers.append(SplitFlow(config=config))

    if squeeze_twice:
        flow_layers.append(SqueezeFlow())
        flow_layers += [CouplingLayer(network=GatedConvNet(c_in=8*config.c, c_hidden=64),
                                      mask=create_channel_mask(c_in=8*config.c, invert=(i % 2 == 1)),
                                      c_in=8*config.c) for i in range(4)]

        sample_shape_factor = torch.tensor([1, 8, 0.25, 0.25])

    else:
        flow_layers += [CouplingLayer(network=GatedConvNet(c_in=2*config.c, c_hidden=64),
                                      mask=create_channel_mask(c_in=2*config.c, invert=(i % 2 == 1)),
                                      c_in=2*config.c) for i in range(4)]

        sample_shape_factor = torch.tensor([1, 2, 0.5, 0.5])

    flow_model = ImageFlow(flow_layers, config=config)
    return flow_model, sample_shape_factor


def create_flow(config):
    create_flow_func = eval(f"create_{config.model_name}_flow")
    try:
        net, sample_shape_factor = create_flow_func(config=config)
    except NameError:
        raise NameError(f"Unknown model: {config.model_name}")

    net = net.to(device=config.device)
    print(f"Done Creating Network! (model: {config.model_name})")
    return net, sample_shape_factor
