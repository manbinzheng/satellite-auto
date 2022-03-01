import os
from time import sleep
import cfscrape
from eth_account.messages import encode_defunct
from eth_account import Account
import uuid
import json

from terra_sdk.client.lcd import LCDClient
from terra_sdk.key.mnemonic import MnemonicKey
from terra_sdk.client.lcd.wallet import Wallet
from terra_sdk.core.coin import Coin
from terra_sdk.core.coins import Coins
from terra_sdk.key.raw import RawKey
from terra_sdk.client.lcd.api.tx import CreateTxOptions
from terra_sdk.core.bank import MsgSend
from terra_sdk.core.fee import Fee
from terra_sdk.core.ibc_transfer.msgs import MsgTransfer
from terra_sdk.core.ibc.data.client import Height
from terra_sdk.core.numeric import Numeric

from web3 import HTTPProvider, Web3

ACCOUNT_RUN_COUNT = 1       # 一个账户操作次数
RUN_ACCOUNT_COUNT = 3       # 操作账户个数

# terra lcd地址和chain id
TERRA_LCD = "https://terra.stakesystems.io"
TERRA_CHAIN_ID = "columbus-5"

# polygon rpc地址
POLYGON_RPC = "https://matic-mainnet.chainstacklabs.com" 

# polygon上satellite luna跨链交易合约
POLYGON_SATELLITE_CONTRACT = "0xa17927fb75e9faea10c08259902d0468b3dead88" 



# polygon 账户private key
POLYGON_ACCOUNT_PRIVATE_KEY = ""
# terra 账户助记词
TERRA_ACCOUNT_MNEMONIC = ""


"""
    请求跨链目标发送地址
    private_key polygon钱包私钥
    terra_address terra钱包地址
    当为terra_address空时，表示生成从terra->polygon跨链生成的terra地址
    如果terra_address有值，表示生成从polygon->terra跨链生成的polygon地址
"""
def get_asset_address(private_key, terra_address = ""):
    # 使用cfscrape库绕过cloudflare
    scraper = cfscrape.create_scraper()

    # 请求otc和validationMsg
    url = "https://bridge-rest-server.mainnet.axelar.dev/getOneTimeCode?publicAddress=0x6A8C82AB24Fa054AE4B749A943468E5C62a23B36"
    res = scraper.get(url).content
    json_ret = json.loads(res)
    
    # 初始化ethAccount并对validationMsg进行签名
    account = Account.privateKeyToAccount(private_key)
    ret = account.sign_message(encode_defunct(text=json_ret['validationMsg']))

    # 获得signature、otc、public_address、trace_id
    signature = ret.signature.hex()
    otc = json_ret['otc']
    public_address = account._address
    trace_id = str(uuid.uuid4())

    # 模拟请求，获取目标assetAddress
    header = {"otc": otc,"publicaddress": public_address,"signature": signature,"x-traceid": trace_id}
    json_data = '{"sourceChainInfo":{"chainSymbol":"Terra","chainName":"Terra","estimatedWaitTime":5,"fullySupported":true,"txFeeInPercent":0.1,"module":"axelarnet"},"selectedSourceAsset":{"assetSymbol":"LUNA","assetName":"LUNA","minDepositAmt":0.005,"common_key":"uluna","native_chain":"terra","decimals":6,"fullySupported":true},"destinationChainInfo":{"chainSymbol":"POLYGON","chainName":"Polygon","estimatedWaitTime":15,"fullySupported":true,"txFeeInPercent":0.1,"module":"evm","confirmLevel":225},"selectedDestinationAsset":{"assetAddress":"'+public_address+'","assetSymbol":"LUNA","common_key":"uluna"},"signature":"'+signature+'","otc":"'+otc+'","publicAddr":"'+public_address+'","transactionTraceId":"'+trace_id+'"}'
    # 如果有terra_address参数，则表示生成从polygon->terra跨链生成的polygon地址
    if(terra_address):
        json_data = '{"sourceChainInfo":{"chainSymbol":"POLYGON","chainName":"Polygon","estimatedWaitTime":15,"fullySupported":true,"txFeeInPercent":0.1,"module":"evm","confirmLevel":225},"selectedSourceAsset":{"assetSymbol":"LUNA","assetName":"LUNA (Axelar-wrapped)","minDepositAmt":0.5,"common_key":"uluna","native_chain":"terra","decimals":6,"fullySupported":true},"destinationChainInfo":{"chainSymbol":"Terra","chainName":"Terra","estimatedWaitTime":5,"fullySupported":true,"txFeeInPercent":0.1,"module":"axelarnet"},"selectedDestinationAsset":{"assetAddress":"'+terra_address+'","assetSymbol":"LUNA","common_key":"uluna"},"signature":"'+signature+'","otc":"'+otc+'","publicAddr":"'+public_address+'","transactionTraceId":"'+trace_id+'"}'
    json_data = json.loads(json_data)
    res = scraper.post("https://bridge-rest-server.mainnet.axelar.dev/transferAssets",json=json_data,headers=header).content
    json_ret = json.loads(res)
    asset_address = json_ret['assetInfo']['assetAddress']
    return asset_address

"""
    发送Luna余额
"""
def send_luna(sender_key, to_address):
    terra = LCDClient(chain_id = TERRA_CHAIN_ID, url = TERRA_LCD)

    sender = terra.wallet(sender_key)
    print("账户: " + sender.key.acc_address)

    # 获取余额
    luna_balance = 0
    while(1):
        balance_info = terra.bank.balance(sender.key.acc_address)
        if len(balance_info[0]) > 0 and balance_info[0].get("uluna") != None:
            current_luna_balance = (int)(balance_info[0].get("uluna").amount)
            print(current_luna_balance)
            if luna_balance == 0:
                luna_balance = current_luna_balance
            elif current_luna_balance > luna_balance:
                luna_balance = current_luna_balance
                print("luna已到账")
                break
            else:
                print("luna未到账, 10秒后重试")
                sleep(10)
        
    if luna_balance < 500000:
        print("Terra 账户luna尚未到账")
        return -1

    # 普通交易
    msg = MsgSend(
        from_address = sender.key.acc_address,
        to_address = to_address,
        amount = Coins(str(luna_balance-2250) + "uluna")
    )
    
    # 创建并签名交易
    tx = sender.create_and_sign_tx(
        CreateTxOptions(
            msgs = [msg],
            fee = Fee(150000, "2250uluna"), # gas limit 和 gas prices
            gas = 'auto'
        )
    )

    # 广播交易
    print("等待交易打包...")
    result = terra.tx.broadcast(tx)
    if result.code == 0:
        print("交易成功")
    else:
        print("交易失败，点击查看 https://finder.terra.money/mainnet/tx/" + result.txhash)


"""
    跨链发送luna 从 Terra 到 Polygon
"""
def send_luna_from_terra_to_polygon(sender_key):
    terra = LCDClient(chain_id = TERRA_CHAIN_ID, url = TERRA_LCD)

    # # 初始化钱包
    # mnemonic_key = MnemonicKey(mnemonic = TERRA_ACCOUNT_MNEMONIC)
    sender = terra.wallet(sender_key)

    print("账户: " + sender.key.acc_address)

    # 获取余额
    luna_balance = 0
    balance_info = terra.bank.balance(sender.key.acc_address)
    if len(balance_info[0]) > 0 and balance_info[0].get("uluna") != None:
        luna_balance = (int)(balance_info[0].get("uluna").amount)
        print("账户余额: " + str(luna_balance) + "uluna")
        
    if luna_balance < 500000:
        print("Terra 账户luna余额不足")
        return -1

    # 请求Satellite接受地址
    print("开始请求Satellite receiver...")
    receiver = get_asset_address(POLYGON_ACCOUNT_PRIVATE_KEY)
    print("Satellite receiver: " + receiver)

    # 发送IBC交易
    ibc_msg = MsgTransfer(
        source_port = "transfer",
        source_channel = "channel-19",
        token = "500000uluna",
        sender = sender.key.acc_address,
        receiver = receiver,
        timeout_height = Height(revision_height = 10, revision_number = 10),
        timeout_timestamp = "0"
    )

    # 创建并签名交易
    tx = sender.create_and_sign_tx(
        CreateTxOptions(
            msgs = [ibc_msg],
            fee = Fee(150000, "2250uluna"), # gas limit 和 gas prices
            gas = 'auto'
        )
    )
    print("等待交易打包...")
    # 广播交易
    result = terra.tx.broadcast(tx)
    
    if result.code == 0:
        print("交易成功")
        return result
    else:
        print("交易失败，点击查看 https://finder.terra.money/mainnet/tx/" + result.txhash)
        return

"""
    跨链发送luna 从 Polygon 到 Terra
"""
def send_luna_from_polygon_to_terra(to_address):
    web3 = Web3(HTTPProvider(POLYGON_RPC))

    # 初始化钱包
    account = web3.eth.account.from_key(POLYGON_ACCOUNT_PRIVATE_KEY)
    print("账户: " + account.address)

    # 获取交易input data
    satellite_abi = """
    [
        {
            "inputs": [
                {
                    "internalType": "address",
                    "name": "recipient",
                    "type": "address"
                },
                {
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256"
                }
            ],
            "name": "transfer",
            "outputs": [
                {
                    "internalType": "bool",
                    "name": "",
                    "type": "bool"
                }
            ],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "address",
                    "name": "",
                    "type": "address"
                }
            ],
            "name": "balanceOf",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    """
    contract = web3.eth.contract(web3.toChecksumAddress(POLYGON_SATELLITE_CONTRACT), abi = satellite_abi)

    # 查询余额
    luna_balance = (int)(contract.functions.balanceOf(account.address).call())
    if luna_balance < 499500:
        print("luna尚未到账")
        return -1
    print("luna已到账!!")
    # 请求Satellite接受地址
    print("开始请求Satellite receiver...")
    receiver = get_asset_address(POLYGON_ACCOUNT_PRIVATE_KEY, to_address)
    print("Satellite receiver: " + receiver)

    input_data = contract.functions.transfer(receiver, luna_balance)._encode_transaction_data()
    sign_tx = web3.eth.account.sign_transaction({
        "chainId" : 137,
        "from" : web3.toChecksumAddress(account.address),
        "to" : web3.toChecksumAddress(POLYGON_SATELLITE_CONTRACT),
        "nonce" : web3.eth.get_transaction_count(account.address),
        "gas" : 100000,
        "maxFeePerGas" : web3.toWei("33", "gwei"),
        "maxPriorityFeePerGas" : web3.toWei("33", "gwei"),
        "data" : input_data
    }, POLYGON_ACCOUNT_PRIVATE_KEY)

    tx_hash = web3.eth.send_raw_transaction(sign_tx.rawTransaction)
    print("tx_hash = " + tx_hash.hex())
    print("等待交易打包...")
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash,600)
    if tx_receipt.status == 1:
        print("交易成功")
        return tx_receipt
    else:
        print("交易失败，点击查看 https://polygonscan.com/tx/" + tx_hash.hex())
        return


"""
    将执行成功的账号记录到account.json文件下
"""
def write(index,account):
    file_name = "account.json"
    load_dict = []
    if os.path.exists(file_name):
        with open(file_name,'r') as load_f:
            load_dict = json.load(load_f)
    load_dict.append({'index':index,'account':account})
    with open("account.json","w") as f:
        json.dump(load_dict,f)

def run(account_index):
    sender_key = MnemonicKey(mnemonic = TERRA_ACCOUNT_MNEMONIC, account=0, index=account_index)

    # 判断是否首个账号，如果不是，就从上一个账号转钱到当前账号操作
    if account_index > 0:
        print("开始从上一个账号转账到当前账号...")
        last_sender_key =  MnemonicKey(mnemonic = TERRA_ACCOUNT_MNEMONIC, account = 0, index = account_index-1)
        send_luna(last_sender_key, sender_key.acc_address)
        print("从上一个账号转账成功")

    # 从terra转币到polygon
    print("开始从terra转币到polygon")
    to_polygon_ret = None    
    while(1):
        to_polygon_ret = send_luna_from_terra_to_polygon(sender_key)
        if to_polygon_ret == -1: # 未到账，重试
            print("等待10秒后重试")
            sleep(10)
            continue
        break

    # 从polygon转币到terra
    print("开始从polygon转币到terra")
    to_terra_ret = None
    if to_polygon_ret != None and to_polygon_ret != -1:
        while(1):
            to_terra_ret = send_luna_from_polygon_to_terra(sender_key.acc_address)
            if to_terra_ret == -1: # 未到账，重试
                print("等待10秒后重试")
                sleep(10)
                continue
            break
    
    if to_terra_ret != None:
        write(account_index, sender_key.private_key.hex())
    
   
def main():
    for account_index in range(RUN_ACCOUNT_COUNT):
        print("操作账户index:" + str(account_index))
        for i in range(ACCOUNT_RUN_COUNT):
            run(account_index)
            # try:
                
            # except Exception as e:
            #     print(repr(e))

    # 将最后一个账户的余额转回第一个账户
    print("开始将余额转回第一个账号...")
    sender_key =  MnemonicKey(mnemonic = TERRA_ACCOUNT_MNEMONIC, account = 0, index = RUN_ACCOUNT_COUNT - 1)
    first_key = MnemonicKey(mnemonic = TERRA_ACCOUNT_MNEMONIC, account = 0, index = 0)
    send_luna(sender_key, first_key.acc_address)
    print("转账成功")

    print("脚本执行完成，剩余LUNA将在account.json最后一个账号，由于跨链需要时间，请耐心等待！")
main()

