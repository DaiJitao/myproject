import torch
import torch.nn as nn
import torch.nn.init as init
import torch.utils.model_zoo as model_zoo
from C4.utils import *
import sys

__all__ = ['SqueezeNet', 'squeezenet1_0', 'squeezenet1_1']

model_urls = {
    'squeezenet1_0': 'https://download.pytorch.org/models/squeezenet1_0-a815701f.pth',
    'squeezenet1_1': 'https://download.pytorch.org/models/squeezenet1_1-f364aa15.pth',
}


class Fire(nn.Module):

    def __init__(self, inplanes, squeeze_planes,
                 expand1x1_planes, expand3x3_planes):
        super(Fire, self).__init__()
        self.inplanes = inplanes
        self.squeeze = nn.Conv2d(inplanes, squeeze_planes, kernel_size=1)
        self.squeeze_activation = nn.ReLU(inplace=True)
        self.expand1x1 = nn.Conv2d(squeeze_planes, expand1x1_planes,
                                   kernel_size=1)
        self.expand1x1_activation = nn.ReLU(inplace=True)
        self.expand3x3 = nn.Conv2d(squeeze_planes, expand3x3_planes,
                                   kernel_size=3, padding=1)
        self.expand3x3_activation = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.squeeze_activation(self.squeeze(x))
        return torch.cat([
            self.expand1x1_activation(self.expand1x1(x)),
            self.expand3x3_activation(self.expand3x3(x))
        ], 1)


class SqueezeNet(nn.Module):

    def __init__(self, version=1.0, num_classes=1000):
        super(SqueezeNet, self).__init__()
        if version not in [1.0, 1.1]:
            raise ValueError("Unsupported SqueezeNet version {version}:"
                             "1.0 or 1.1 expected".format(version=version))
        self.num_classes = num_classes
        if version == 1.0:
            self.features = nn.Sequential(
                nn.Conv2d(3, 96, kernel_size=7, stride=2),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(96, 16, 64, 64),
                Fire(128, 16, 64, 64),
                Fire(128, 32, 128, 128),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(256, 32, 128, 128),
                Fire(256, 48, 192, 192),
                Fire(384, 48, 192, 192),
                Fire(384, 64, 256, 256),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(512, 64, 256, 256),
            )
        else:
            self.features = nn.Sequential(
                nn.Conv2d(3, 64, kernel_size=3, stride=2),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(64, 16, 64, 64),
                Fire(128, 16, 64, 64),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(128, 32, 128, 128),
                Fire(256, 32, 128, 128),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(256, 48, 192, 192),
                Fire(384, 48, 192, 192),
                Fire(384, 64, 256, 256),
                Fire(512, 64, 256, 256),
            )
        # Final convolution is initialized differently form the rest
        final_conv = nn.Conv2d(512, self.num_classes, kernel_size=1)
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.5),
            final_conv,
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                if m is final_conv:
                    init.normal_(m.weight, mean=0.0, std=0.01)
                else:
                    init.kaiming_uniform_(m.weight)
                if m.bias is not None:
                    init.constant_(m.bias, 0)

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x.view(x.size(0), self.num_classes)


def squeezenet1_0(pretrained=False, **kwargs):
    r"""SqueezeNet model architecture from the `"SqueezeNet: AlexNet-level
    accuracy with 50x fewer parameters and <0.5MB model size"
    <https://arxiv.org/abs/1602.07360>`_ paper.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = SqueezeNet(version=1.0, **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['squeezenet1_0']))
    return model


def squeezenet1_1(pretrained=False, **kwargs):
    r"""SqueezeNet 1.1 model from the `official SqueezeNet repo
    <https://github.com/DeepScale/SqueezeNet/tree/master/SqueezeNet_v1.1>`_.
    SqueezeNet 1.1 has 2.4x less computation and slightly fewer parameters
    than SqueezeNet 1.0, without sacrificing accuracy.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = SqueezeNet(version=1.1, **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['squeezenet1_1']))
    return model


class CreateNet(nn.Module):
    def __init__(self, model, resnet=None):
        self.is_resnet = False
        super(CreateNet, self).__init__()
        self.squeezenet1_1 = nn.Sequential(*list(model.children())[0][:12])
        if resnet is not None:
            self.is_resnet = True
            model = resnet
            self.resnet1 = nn.Sequential(*list(model.children())[:8])

            self.feature2 = nn.Sequential(
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(128, 32, 128, 128),
                Fire(256, 32, 128, 128),
                nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
                Fire(256, 48, 192, 192),
                Fire(384, 48, 192, 192),
                Fire(384, 64, 256, 256),
                Fire(512, 64, 256, 256),)
            self.num_classes = 1000

            final_conv = nn.Conv2d(512, self.num_classes, kernel_size=1)
            self.classifier = nn.Sequential(
                nn.Dropout(p=0.5),
                final_conv,
                nn.ReLU(inplace=True),
                nn.AdaptiveAvgPool2d((1, 1))
            )

        self.fc = nn.Sequential(
            nn.MaxPool2d(kernel_size=3, stride=2, ceil_mode=True),
            nn.Conv2d(512, 64, kernel_size=6, stride=1, padding=3),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.5),
            nn.Conv2d(64, 3, kernel_size=1, stride=1),
            nn.ReLU(inplace=True))

    def forward(self, x):
        if not self.is_resnet:
            x = self.squeezenet1_1(x) # [16,3,256,256]
            x = self.fc(x)
            return x
        else:
            x = self.resnet1(x) # reset [16, 512, 8, 8]
            res = x.repeat([1, 1, 8, 8])
            conv = torch.nn.Conv2d(in_channels=512, out_channels=128, kernel_size=2)(res)
            x = self.feature2(conv) # Fire model [16, 512, 8, 8]

            x = self.fc(x)
            return x


class CreateNet_3stage(nn.Module):
    def __init__(self, num_model=2):
        super(CreateNet_3stage, self).__init__()
        self.submodel1 = CreateNet(squeezenet1_1(pretrained=True))
        self.submodel2 = CreateNet(squeezenet1_1(pretrained=True))
        self.submodel3 = CreateNet(squeezenet1_1(pretrained=True))

    def forward(self, x):  # x[bs,3,h,w]
        output1 = self.submodel1(x)
        pred1 = torch.sum(torch.sum(output1, 2), 2)

        pred1 = torch.nn.functional.normalize(pred1, dim=1)
        correct_img1 = correct_image_nolinear(x, pred1)
        output2 = self.submodel2(correct_img1)
        pred2 = torch.sum(torch.sum(output2, 2), 2)
        pred2 = torch.nn.functional.normalize(pred2, dim=1)
        correct_img2 = correct_image_nolinear(x, torch.mul(pred1, pred2))
        output3 = self.submodel3(correct_img2)
        pred3 = torch.sum(torch.sum(output3, 2), 2)
        pred3 = torch.nn.functional.normalize(pred3, dim=1)
        return pred1, pred2, pred3


if __name__ == '__main__1':
    network = CreateNet_1().cuda()
    input = torch.randn([16, 3, 256, 256]).cuda()
    label = torch.randn([16, 3]).cuda()
    pred = network(input)

if __name__ == '__main__1':
    # kernel_size = 3
    # pool = torch.nn.MaxPool2d(kernel_size, stride=2, padding=0, dilation=1, ceil_mode=True)
    #
    # input = torch.randn([16, 128, 63, 63])
    # res = pool(input)
    # print(res.shape)

    conv = torch.nn.Conv2d(in_channels=512, out_channels=128, kernel_size=2, stride=1, padding=0)

    input = torch.randn([16, 512, 8, 8])
    res = input.repeat([1,1, 8, 8])
    print(res.shape)
    res = conv(res)
    print(res.shape)

if __name__ == '__main__':
    import torchvision
    from torchvision.models import resnet18, resnet101, resnet34
    from torch import nn
    from torch import optim
    from torchinfo import summary

    input = torch.randn([32, 3, 256, 256])
    resnet = resnet34(pretrained=True)
    SqueezeNet = squeezenet1_1(pretrained=True)
    layers = list(SqueezeNet.children())
    print(len(layers[0]))

    network = CreateNet(SqueezeNet,None)

    label = torch.randn([16, 3])
    pred = network(input)
    print(pred.shape)

if __name__ == '__main__1':
    network = CreateNet_1()
    input = torch.randn([16, 3, 256, 256]).cuda()
    label = torch.randn([16, 3]).cuda()
    pred = network(input)
