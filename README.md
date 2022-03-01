# Satellite交互空投自动化脚本


### 使用前准备
- #### 开发者环境
	>python 3.8.0</br>
	 pip 19.2.3
- #### 账户准备
	>Terra账户助记词1个。</br>
	 Polygon账户私钥1个。
- #### 资金准备
	>Terra默认账户中需要至少0.55个LUNA（每次Terra跨链转出需要至少0.5个LUNA，剩余的充当手续费）</br>
	Polygon账户中需要准备至少0.1个MATIC(充当手续费)

---

### 脚本运行逻辑
- 由Terra账户助记词生成指定个数的账户。
从第一个Terra账户转0.5LUNA至Polygon账户（Satellite要求Terra跨链转出至少0.5LUNA），再把Polygon到账的LUNA转回该Terra账户。
然后把该Terra账户的所有LUNA转入第二个Terra账户，再完成一次与Polygon的跨链操作。
以此循环至账户内余额小于0.5LUNA或者gas费不足。
- 注：跨链操作除了gas费损耗，还有一定的本金损耗。<br/>
	笔者测试损耗结果如下：<br/>
	Terra->Polygon转0.5LUNA实际到账0.4995LUNA<br/>
	Polygon->Terra转回0.4995LUNA实际到账0.4990LUNA
---


### 脚本使用

#### 1. 安装依赖包

```bash
pip3 install -r requirements.txt
```

#### 2. 脚本配置

- 在main.py顶部找到以下变量
```bash


ACCOUNT_RUN_COUNT = 1  # 一个账户操作次数
RUN_ACCOUNT_COUNT = 3  # 操作账户个数


POLYGON_ACCOUNT_PRIVATE_KEY = ""  # Polygon 账户private key
TERRA_ACCOUNT_MNEMONIC = ""  # Terra 账户助记词
```

#### 3. 执行脚本

```bash
python3 main.py
```