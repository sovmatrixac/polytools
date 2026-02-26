import requests  
  
def get_market_info():  
    response = requests.get(  
        "https://gamma-api.polymarket.com/markets",  
        params={"active": "true", "closed": "false", "limit": 100000}  
    ) 

    markets = response.json()  
    print (type(markets[1]))
    market = markets[99] 
    sorted_markets = sorted(
    	markets,
    	key=lambda x: x['lastTradePrice'],
    	reverse=True
    )

    print(sorted_markets[0])

    print(f"Question: {market['question']}")  
    print(f"Condition ID: {market['conditionId']}")  
    print(f"Token IDs (Yes, No): {market['clobTokenIds']}")  
    # ['123...', '456...']  
  
    return market  
  
get_market_info()  

