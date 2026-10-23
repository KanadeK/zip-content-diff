# zip-content-diff 中文说明

在本地比较 ZIP、wheel、JAR 等发布文件。逐项读取成员并计算 SHA-256，区分内容变化与
时间戳、压缩方式、文件属性、注释、顺序等变化，全程不解压到磁盘、不执行成员文件。

需要 Python 3.11+，无运行时依赖。创建并激活虚拟环境后：

```console
python -m pip install .
python scripts/demo.py
zip-content-diff old.zip new.zip --json
zip-content-diff old.zip new.zip --strict
```

默认内容一致退出 0，内容变化退出 1；`--strict` 对任何字节变化退出 1，适合可复现构建。
元数据变化（包括权限）也可能影响使用，不能把默认内容一致当作整个发布文件完全等价。
损坏、超出限制、重复成员名、不支持的压缩或加密返回 2。

默认每个压缩包不超过 64 MiB、10,000 个成员，解压总量不超过 256 MiB，另有单成员、
压缩比和协作式时间限制。支持 STORE/DEFLATE。报告包含成员名与哈希，不包含文件内容；
仍应注意报告保密。不是沙箱或恶意软件扫描工具，不递归比较嵌套压缩包。

卸载：`python -m pip uninstall zip-content-diff`。没有全局状态或缓存。
详细规则及限制见 [English README](README.md)。MIT 许可证。
