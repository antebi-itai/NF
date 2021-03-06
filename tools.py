import os
import torch
import torchvision
import numpy as np
import matplotlib.pyplot as plt
import math
from math import log10, floor


# Plotting images


def imgs_to_plt(imgs, title=None, row_size=4):
    # Form a grid of pictures (we use max. 8 columns)
    num_imgs = imgs.shape[0] if isinstance(imgs, torch.Tensor) else len(imgs)
    is_int = imgs.dtype == torch.int32 if isinstance(imgs, torch.Tensor) else imgs[0].dtype == torch.int32
    nrow = min(num_imgs, row_size)
    ncol = int(math.ceil(num_imgs/nrow))
    imgs = torchvision.utils.make_grid(imgs, nrow=nrow, pad_value=128 if is_int else 0.5)
    np_imgs = imgs.cpu().numpy()
    # Plot the grid
    plt.figure(figsize=(1.5*nrow, 1.5*ncol))
    plt.imshow(np.transpose(np_imgs, (1, 2, 0)), interpolation='nearest')
    plt.axis('off')
    if title is not None:
        plt.title(title)


def sample_save_show(flow, img_shape, sample_shape_factor, config):
    # sample
    batched_img_shape = torch.cat((torch.tensor([config.num_samples]), torch.tensor(img_shape)))
    sample_shape = torch.Size((batched_img_shape * sample_shape_factor).int())
    samples = flow.sample(sample_shape=sample_shape).cpu()

    # samples to plt
    imgs_to_plt(imgs=samples, row_size=math.ceil(math.sqrt(config.num_samples)))
    # save
    if config.save_samples:
        plt.savefig(config.results_filepath)
        print(f"Figure saved to {config.results_filepath}")
    # show
    if config.show_samples:
        plt.show()
    plt.close()


# Plotting histogram


def num_bins(x):
    q25, q75 = np.percentile(x, [25, 75])
    bin_width = 2 * (q75 - q25) * len(x) ** (-1/3)
    bins = round((x.max() - x.min()) / bin_width)
    return bins


def plot_hist(x):
    bins = num_bins(x)
    plt.hist(x, bins=bins)
    plt.show()


# Masks for Coupling Layer


def create_checkerboard_mask(h, w, invert=False):
    h_range, w_range = torch.arange(h, dtype=torch.int32), torch.arange(w, dtype=torch.int32)
    hh, ww = torch.meshgrid(h_range, w_range, indexing='ij')
    mask = torch.fmod(hh + ww, 2)
    mask = mask.to(torch.float32).view(1, 1, h, w)
    if invert:
        mask = 1 - mask
    return mask


def create_channel_mask(c_in, invert=False):
    mask = torch.cat([torch.ones(c_in//2, dtype=torch.float32),
                      torch.zeros(c_in-c_in//2, dtype=torch.float32)])
    mask = mask.view(1, c_in, 1, 1)
    if invert:
        mask = 1 - mask
    return mask


def visualize_masks():
    checkerboard_mask = create_checkerboard_mask(h=8, w=8).expand(-1, 2, -1, -1)
    channel_mask = create_channel_mask(c_in=2).expand(-1, -1, 8, 8)

    show_imgs(checkerboard_mask.transpose(0, 1), "Checkerboard mask")
    show_imgs(channel_mask.transpose(0, 1), "Channel mask")


def print_num_params(model):
    num_params = sum([np.prod(p.shape) for p in model.parameters()])
    print("Number of parameters: {:,}".format(num_params))


@torch.no_grad()
def interpolate(model, img1, img2, num_steps=8):
    """
    Inputs:
        model - object of ImageFlow class that represents the (trained) flow model
        img1, img2 - Image tensors of shape [1, 28, 28]. Images between which should be interpolated.
        num_steps - Number of interpolation steps. 8 interpolation steps mean 6 intermediate pictures besides img1 and img2
    """
    imgs = torch.stack([img1, img2], dim=0).to(model.device)
    z, _ = model.encode(imgs)
    alpha = torch.linspace(0, 1, steps=num_steps, device=z.device).view(-1, 1, 1, 1)
    interpolations = z[0:1] * alpha + z[1:2] * (1 - alpha)
    interp_imgs = model.sample(interpolations.shape[:1] + imgs.shape[1:], z_init=interpolations)
    show_imgs(interp_imgs, row_size=8)


def round_to_n(x, n=2):
    if x == 0:
        return 0
    return round(x, -int(floor(log10(abs(x)))) + (n - 1))


def tensor_limits(tensor):
    return round_to_n(tensor.min().item()), \
           round_to_n(tensor.max().item()), \
           round_to_n(tensor.abs().min().item()), \
           round_to_n(tensor.abs().max().item())


def regular_tensor(tensor):
    info_func = torch.finfo if tensor.is_floating_point() else torch.iinfo

    if tensor.isinf().all():
        print("Tensor has only INFs")
    elif tensor.isnan().all():
        print("Tensor has only NANs")
    elif (tensor == info_func(tensor.dtype).min).all():
        print(f"Tensor has only MIN {tensor.dtype}: {round_to_n(info_func(tensor.dtype).min)}")
    elif (tensor == info_func(tensor.dtype).max).all():
        print(f"Tensor has only MAX {tensor.dtype}: {round_to_n(info_func(tensor.dtype).max)}")

    reg_tensor = not (tensor.isinf().any() or
                      tensor.isnan().any() or
                      (tensor == info_func(tensor.dtype).min).any() or
                      (tensor == info_func(tensor.dtype).max).any())
    return reg_tensor


def print_result(result):
    print(f"Loaded Result! \n"
          f"Test: {round_to_n(result['test'][0]['test_bpd'], n=3)} \t"
          f"Val:  {round_to_n(result['val'][0]['test_bpd'], n=3)} \t "
          f"Time: {round_to_n(result['time'], n=3)}")


def make_cuda_visible(gpu_num=0):
    if os.environ['CUDA_VISIBLE_DEVICES'] == '':
        print(f"Running from pycharm... ", end="")
        os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_num)
    else:
        print(f"Running from shell... ", end="")
    print(f"GPU #{os.environ['CUDA_VISIBLE_DEVICES']}")
