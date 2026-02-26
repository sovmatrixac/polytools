import os  
from dotenv import load_dotenv  
from py_clob_client.client import ClobClient  
from py_clob_client.clob_types import OrderArgs  
from py_clob_client.order_builder.constants import BUY, SELL  
from py_builder_signing_sdk.config import BuilderConfig, BuilderApiKeyCreds  
  
load_dotenv() # 用于加载 .env 文件  
  
def main():  
    # --- 1. 配置 ---  
    host = "https://clob.polymarket.com"  
    chain_id = 137 # Polygon Mainnet  
    private_key = os.getenv("PRIVATE_KEY") # **你的 EOA 私钥** (用于签名，非 Builder Key)  
    funder_address = os.getenv("FUNDER_ADDRESS") # **你的 Polymarket 代理钱包地址**  

    print("pk", private_key)
    print("fa", funder_address) 
 
    if not private_key or not funder_address:  
        raise ValueError("请在 .env 文件中配置 PRIVATE_KEY 和 FUNDER_ADDRESS")  
  
    # --- 2. 用户 L1 -> L2 凭证派生 ---  
    temp_client = ClobClient(host, key=private_key, chain_id=chain_id)  
    user_api_creds = temp_client.create_or_derive_api_creds()  
  
    # --- 3. 配置 Builder 凭证 ---  
    builder_creds = BuilderApiKeyCreds(  
        key=os.getenv("POLY_BUILDER_API_KEY"),  
        secret=os.getenv("POLY_BUILDER_SECRET"),  
        passphrase=os.getenv("POLY_BUILDER_PASSPHRASE"),  
    )  
    builder_config = BuilderConfig(local_builder_creds=builder_creds)  
  
    # --- 4. 初始化最终交易客户端 ---  
    client = ClobClient(  
        host,  
        key=private_key,  
        chain_id=chain_id,  
        creds=user_api_creds,  
        signature_type=1, # **关键：邮箱登录用户使用 signature_type = 1**  
        funder=funder_address, # **关键：你的 Polymarket 代理钱包地址**  
        builder_config=builder_config # **关键：传入 Builder 配置**  
    )  
  
    print("ClobClient 初始化成功 (Builder 模式)！")  
    
    # --- 5. 下单演示 ---  
    market_condition_id = "0xaf9d0e448129a9f657f851d49495ba4742055d80e0ef1166ba0ee81d4d594214" # 替换为目标市场的 condition_id  
    no_token_id = "4153292802911610701832309484716814274802943278345248636922528170020319407796" # 替换为 "No" 结果的 token_id  
  
    # 获取 tickSize 和 negRisk  
    market_details = client.get_market(market_condition_id)
    print(market_details)
    tick_size = str(market_details["minimum_tick_size"]) # e.g., "0.01"  
    neg_risk = market_details["neg_risk"] # e.g., False  
  
    # 下一个卖单 (Sell No, 相当于看好 Yes)  
    try:  
        sell_order_response = client.create_and_post_order(  
            OrderArgs(  
                token_id=no_token_id,  
                price=0.50, # 价格  
                size=5,     # 数量 (1 share)  
                side=BUY  
            )  
            #options={"tick_size": tick_size, "neg_risk": neg_risk}  
        )  
        print(f"卖单提交成功: {sell_order_response}")  
    except Exception as e:  
        print(f"卖单提交失败: {e}")  
  
  
if __name__ == "__main__":  
    main()  
