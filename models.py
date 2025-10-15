# models.py
from pydantic import BaseModel
from typing import List, Optional

class Product(BaseModel):
    """商品情報を表すモデル"""
    prd_id: int
    prd_code: str
    prd_name: str
    prd_price: int

class ProductSearchResponse(BaseModel):
    """商品検索APIのレスポンスモデル"""
    product: Optional[Product] = None

class PurchaseItem(BaseModel):
    """購入リスト内の単一商品を表すモデル"""
    prd_id: int
    prd_code: str
    prd_name: str
    prd_price: int

class PurchaseRequest(BaseModel):
    """購入APIのリクエストボディを表すモデル"""
    emp_cd: Optional[str] = ""
    store_cd: str
    pos_no: str
    items: List[PurchaseItem]

class PurchaseResponse(BaseModel):
    """購入APIのレスポンスモデル"""
    success: bool
    total_amount: int
    total_amount_ex_tax: int