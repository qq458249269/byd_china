# BYD China

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![HomeAssistant][ha-badge]][hass]

_Home Assistant 自定义组件，用于接入比亚迪（中国区）车辆数据。_

## 功能

- 车辆实时状态（续航里程、电量、总里程等）
- 空调控制（开关、温度、风量、除霜等）
- 门锁/车窗/天窗状态
- 胎压监测
- GPS 定位追踪
- 远程控制（锁车/解锁、开关空调、开关窗等）
- 主动刷新按钮（实时数据 / GPS 定位）
- 电池加热控制
- 方向盘加热控制

## 安装

### HACS（推荐）

1. 在 HACS 中点击「自定义仓库」，添加此仓库 URL
2. 类别选择「Integration」
3. 点击「下载」
4. 重启 Home Assistant

### 手动安装

1. 将 `custom_components/byd_china/` 目录复制到 Home Assistant 的 `custom_components/` 目录下
2. 重启 Home Assistant

## 配置

1. 重启后，前往「配置」→「设备与服务」→「添加集成」
2. 搜索「BYD China」
3. 输入账号信息：
   - **手机号**：比亚迪 App 注册手机号
   - **密码**：比亚迪 App 密码
   - **控制 PIN**：6 位数字 PIN（如未设置可留空）
   - **品牌**：王朝/海洋/腾势/仰望/方程豹

## 服务

该集成提供以下服务：

- `byd_china.fetch_realtime` — 手动刷新车辆实时数据
- `byd_china.fetch_gps` — 手动刷新 GPS 定位

## 语言

默认简体中文（zh-Hans），界面文本随 Home Assistant 语言设置自动切换。

## 免责声明

本项目与比亚迪股份有限公司无关。使用本组件需自行承担风险。

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[ha-badge]: https://img.shields.io/badge/Home%20Assistant-2024.6-%2341BDF5
[hass]: https://home-assistant.io
[license-shield]: https://img.shields.io/github/license/qq458249269/byd_china
[releases-shield]: https://img.shields.io/github/v/release/qq458249269/byd_china
[releases]: https://github.com/qq458249269/byd_china/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/qq458249269/byd_china
[commits]: https://github.com/qq458249269/byd_china/commits/main
