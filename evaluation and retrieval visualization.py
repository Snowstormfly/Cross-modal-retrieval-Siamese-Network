import numpy as np
import torch.utils
import torch.nn as nn
from torch.utils.data import dataloader, Dataset
import matplotlib.pyplot as plt
import os
from torchvision import datasets, transforms, models
import mymodel
import cv2
from PIL import Image
import torch
import gc

gc.collect()
torch.cuda.empty_cache()

# a = torch.cuda.is_available()
# print(a)
data_dir = r"D:\RSketch"
input_size = 224
batch_size = 50
num_category = 15
query_num = 0
database_num = 0
data_transforms = {
    'train': transforms.Compose([
        transforms.Resize([input_size, input_size]),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ]),
    'test': transforms.Compose([
        transforms.Resize([input_size, input_size]),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ]),
}


class TestDataset(Dataset):
    def __init__(self, test_dataset):
        self.test_dataset = test_dataset
        self.transform = self.test_dataset.transform
        self.test_label_num = len(self.test_dataset.classes)
        self.test_data = self.test_dataset.imgs
        self.test_datanum = len(self.test_data)
        self.test_dict = dict((i, j) for i, j in self.test_data)
        self.test_dict_list = list(self.test_dict.items())

    def __getitem__(self, index):
        img1, label1 = self.test_dict_list[index][0], self.test_dict_list[index][1]
        if self.transform is not None:
            img = Image.open(img1)
            img = self.transform(img)
        return img, label1, img1

    def __len__(self):
        return self.test_datanum


def resnet_forward(self, x):
    x = self.conv1(x)
    x = self.bn1(x)
    x = self.relu(x)
    x = self.maxpool(x)
    x = self.layer1(x)
    x = self.layer2(x)
    x = self.layer3(x)
    x = self.layer4(x)

    x = self.avgpool(x)
    x = x.view(x.size(0), -1)

    return x


model_pretrained = models.resnet50(pretrained=False)
num_ftrs = model_pretrained.fc.in_features
model_pretrained.fc = nn.Linear(num_ftrs, num_category)
num_cls = model_pretrained.fc.out_features
model = mymodel.myresnet50(model_pretrained, num_cls)
model.load_state_dict(torch.load(r"E:\论文数据集\SBIR\SBRSIR-master\models—S1\models40.pth"))  # 加载模型
# print(model.eval())
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()
for param in model.parameters():
    param.requires_grad = False

# 查询库构建和加载
query_data_path = os.path.join(data_dir, "test", "query")
test_a_datasets = datasets.ImageFolder(query_data_path, data_transforms['test'])
query_datasets = TestDataset(test_a_datasets)
query_loader = torch.utils.data.DataLoader(query_datasets, batch_size=batch_size, shuffle=False)
query_num = 0
query_image_dir = []
for inputs, labels, img in query_loader:
    inputs = inputs.to(device)
    labels = labels.to(device)
    image = img
    query_image_dir.append(image)
    outputs = resnet_forward(model, inputs)
    # print(outputs.shape)
    if query_num == 0:
        query_feature = outputs
        query_labels = labels
        query_inputs = inputs.cpu()
    else:
        query_feature = torch.cat([query_feature, outputs], 0)
        query_labels = torch.cat([query_labels, labels], 0)
        query_inputs = torch.cat([query_inputs, inputs.cpu()], 0)
    query_num = query_num + inputs.size(0)
query_feature = query_feature.cpu().numpy()
query_labels = query_labels.cpu().numpy()
query_img_arr = np.array(query_image_dir).flatten()
# print(type(query_labels))

# 数据库构建和保存
database_path = os.path.join(data_dir, "test", "database")
database_folder = datasets.ImageFolder(database_path, data_transforms['test'])
database_datasets = TestDataset(database_folder)
database_loader = torch.utils.data.DataLoader(database_datasets, batch_size=batch_size, shuffle=False)
database_num = 0
database_image_dir = []
for inputs, labels, img in database_loader:
    inputs = inputs.to(device)
    labels = labels.to(device)
    # image = img
    database_image_dir.append(img)
    # print(image_dir)
    outputs = resnet_forward(model, inputs)
    if database_num == 0:
        database_feature = outputs
        database_labels = labels
        database_inputs = inputs.cpu()
    else:
        database_feature=torch.cat([database_feature, outputs], 0)
        database_labels=torch.cat([database_labels, labels], 0)
        database_inputs=torch.cat([database_inputs, inputs.cpu()], 0)
    database_num = database_num + inputs.size(0)
database_feature = database_feature.cpu().numpy()
database_labels = database_labels.cpu().numpy()
label_exp = np.expand_dims(database_labels, axis=-1)
image_arr = np.array(database_image_dir).flatten()
image_exp = np.expand_dims(image_arr, axis=-1)
# print(image_arr)
all_feature = np.concatenate([database_feature, label_exp, image_exp], axis=-1)
# print(all_feature.shape)
np.save(r"E:\论文数据集\SBIR\database.npy", all_feature)
data = np.load(r"E:\论文数据集\SBIR\database.npy")

# 数据库重新加载
database = np.load(r"E:\论文数据集\SBIR\database.npy")
database_feature = database[:, :-2].astype(np.float32)
# print(len(database_feature))
# print(type(database_feature))
database_label = database[:, 2048:-1].astype(np.float32)
database_img_dir = database[:, -1:]
# print(database_img_dir)

# 检索及结果输出
unseen_labels = [0, 4, 8, 12, 16]
# unseen_labels = [1, 5, 9, 13, 17]
# unseen_labels = [2, 6, 10, 14, 18]
# unseen_labels = [3, 7, 11, 15, 19]
total_precision_list = []
seen_precision_list = []
unseen_precision_list = []
query_label = []
m = 5  # 返回前m个检索结果
f = open(r"E:\论文数据集\SBIR\result3.txt", 'a+')
seg = "----------\n"
for n in range(query_num):
    q_feature = query_feature[n, :]  # 第n个查询图像
    q_label = query_labels[n]  # 第n个查询图像标签
    q_image = query_img_arr[n]  # 第n个查询图像路径
    query_label.append(q_label)
    if q_label in unseen_labels:
        unseen = 1
    else:
        unseen = 0
    con_loss = []
    # f = open(r"E:\论文数据集\SBIR\result3.txt", 'a+')
    f.write(seg)
    f.write("查询图像为：" + str(q_image) + '\n')
    for i in range(len(database_feature)):
        d_feature = database_feature[i, :]
        con_loss = np.append(con_loss, np.linalg.norm(q_feature - d_feature))  # 计算两个模态图像特征损失
    all_index = np.argsort(con_loss)
    index = all_index[:m]  # 取检索靠前的m个结果的索引值
    # print(database_img_dir.dtype)
    ture_match = 0
    f.write("数据库检索结果为：" + '\n')
    for j in index:
        img_path = database_img_dir[j]
        d_label = database_label[j]
        f.write(str(img_path) + '\n')  # 将检索结果输出
        if d_label == q_label:
            ture_match += 1
    precision = ture_match/m
    total_precision_list.append(precision)
    if unseen == 1:
        unseen_precision_list.append(precision)
    else:
        seen_precision_list.append(precision)
unseen_precision_arr = np.array(unseen_precision_list)
seen_precision_arr = np.array(seen_precision_list)
unseen_precision = np.mean(unseen_precision_arr)
seen_precision = np.mean(seen_precision_arr)
total_precision_arr = np.array(total_precision_list)
total_precision = np.mean(total_precision_arr)
print("不可见类为：" + str(unseen_labels))
print("total precisicon: {:.4f} unseen precision: {:.4f} seen precision: {:.4f}".format(total_precision, unseen_precision, seen_precision))
# with open(r"E:\论文数据集\SBIR\result3.txt", 'a+') as f:
f.write(seg)
f.write("不可见类为：" + str(unseen_labels)+'\n')
f.write("total precisicon: {:.4f} unseen precision: {:.4f} seen precision: {:.4f}\n".format(total_precision, unseen_precision, seen_precision))
query_label_arr = np.array(query_label)
q_label_uni = np.unique(query_label_arr)  # 得到所有的分类标签
for n in q_label_uni:
    indexes = np.where(query_label_arr == n)  # 找到第n个分类的所有索引
    class_precision_list = []
    for index in indexes[0]:
        p = total_precision_arr[index]  # 根据分类的索引取出对应的精度
        class_precision_list.append(p)  # 将相同分类的精度添加至同一列表
    class_precision_arr = np.array(class_precision_list)
    class_precision = np.mean(class_precision_arr)  # 计算该分类的平均精度
    # print(class_precision)
    print("class: {}, class precision: {:.4f}".format(n, class_precision))
    f.write("class: {}, class precision: {:.4f}\n".format(n, class_precision))
f.close()
