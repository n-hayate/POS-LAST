"""
POS System Backend API
高速・安全・保守性の高いFastAPIアプリケーション
"""
import os
import math
from datetime import datetime
from contextlib import contextmanager
from typing import List, Optional

import pymysql
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ==================== Configuration ====================
class Config:
    """環境変数から設定を読み込む"""
    DB_HOST = os.environ.get("DB_HOST", "")
    DB_USER = os.environ.get("DB_USER", "")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "https://localhost:3000",
        "https://app-002-gen10-step3-1-node-oshima42.azurewebsites.net",
    ]


# ==================== Pydantic Models ====================
class Product(BaseModel):
    """商品情報"""
    prd_id: int
    prd_code: str
    prd_name: str
    prd_price: int = Field(..., gt=0, description="価格（税込）")


class ProductSearchResponse(BaseModel):
    """商品検索レスポンス"""
    product: Optional[Product] = None


class PurchaseItem(BaseModel):
    """購入商品"""
    prd_id: int
    prd_code: str
    prd_name: str
    prd_price: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0, le=9999, description="購入数量")


class PurchaseRequest(BaseModel):
    """購入リクエスト"""
    emp_cd: Optional[str] = Field(default="", max_length=20)
    store_cd: str = Field(default="30", max_length=20)
    pos_no: str = Field(default="90", max_length=20)
    items: List[PurchaseItem] = Field(..., min_items=1)


class PurchaseResponse(BaseModel):
    """購入レスポンス"""
    success: bool
    total_amount: int
    total_amount_ex_tax: int
    transaction_id: Optional[int] = None


# ==================== Database ====================
@contextmanager
def get_db_connection():
    """データベース接続のコンテキストマネージャ"""
    conn = None
    
    # 環境変数の検証（実行時）
    if not all([Config.DB_HOST, Config.DB_USER, Config.DB_PASSWORD, Config.DB_NAME]):
        print("[エラー] データベース環境変数が設定されていません")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="データベース設定が不完全です"
        )
    
    try:
        conn = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            port=Config.DB_PORT,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
            autocommit=False
        )
        yield conn
    except pymysql.Error as e:
        print(f"[DB接続エラー] {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="データベースに接続できません"
        )
    finally:
        if conn:
            conn.close()


# ==================== FastAPI Application ====================
app = FastAPI(
    title="POS System API",
    version="2.0.0",
    description="モバイルPOSシステム用バックエンドAPI"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ==================== API Endpoints ====================
@app.get("/", tags=["Health"])
def health_check():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "service": "POS System API",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "db_configured": bool(Config.DB_HOST and Config.DB_USER)
    }


@app.post("/search_product", response_model=ProductSearchResponse, tags=["Products"])
def search_product(request_body: dict):
    """
    商品コードから商品情報を検索
    
    Args:
        request_body: {"code": "商品コード"}
    
    Returns:
        商品情報（見つからない場合はproduct=None）
    """
    product_code = request_body.get("code", "").strip()
    
    if not product_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="商品コードが必要です"
        )
    
    print(f"[商品検索] コード: {product_code}")
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    PRD_ID as prd_id,
                    CODE as prd_code,
                    NAME as prd_name,
                    PRICE as prd_price
                FROM m_product
                WHERE CODE = %s
                LIMIT 1
            """
            cursor.execute(query, (product_code,))
            result = cursor.fetchone()
            
            if result:
                print(f"[検索成功] {result['prd_name']}")
                return ProductSearchResponse(product=Product(**result))
            else:
                print(f"[検索失敗] 商品なし")
                return ProductSearchResponse(product=None)


@app.post("/purchase", response_model=PurchaseResponse, tags=["Transactions"])
def purchase(request: PurchaseRequest):
    """
    購入処理を実行
    
    Args:
        request: 購入情報（従業員コード、店舗、POS番号、商品リスト）
    
    Returns:
        購入結果（成功/失敗、合計金額、取引ID）
    """
    print(f"[購入開始] アイテム数: {len(request.items)}")
    
    # 合計金額計算
    total_amount = sum(item.prd_price * item.quantity for item in request.items)
    total_amount_ex_tax = sum(
        math.floor(item.prd_price / 1.1) * item.quantity 
        for item in request.items
    )
    
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cursor:
                # 1. 取引ヘッダー登録
                emp_cd = request.emp_cd or "9999999999"
                
                insert_txn = """
                    INSERT INTO t_txn 
                    (DATETIME, EMP_CD, STORE_CD, POS_NO, TOTAL_AMT, TTL_AMT_EX_TAX)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    insert_txn,
                    (datetime.now(), emp_cd, request.store_cd, request.pos_no,
                     total_amount, total_amount_ex_tax)
                )
                
                trd_id = cursor.lastrowid
                print(f"[取引登録] ID: {trd_id}")
                
                # 2. 取引明細登録
                insert_dtl = """
                    INSERT INTO t_txn_dtl
                    (TRD_ID, DTL_ID, PRD_ID, PRD_CODE, PRD_NAME, PRD_PRICE, TAX_CD)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                dtl_id = 1
                for item in request.items:
                    for _ in range(item.quantity):
                        cursor.execute(
                            insert_dtl,
                            (trd_id, dtl_id, item.prd_id, item.prd_code,
                             item.prd_name, item.prd_price, "10")
                        )
                        dtl_id += 1
                
                conn.commit()
                print(f"[購入成功] 合計: ¥{total_amount:,}")
                
                return PurchaseResponse(
                    success=True,
                    total_amount=total_amount,
                    total_amount_ex_tax=total_amount_ex_tax,
                    transaction_id=trd_id
                )
                
        except pymysql.Error as e:
            conn.rollback()
            print(f"[購入エラー] {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"購入処理に失敗しました: {str(e)}"
            )


# ==================== Azure Entry Point ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"[起動] ポート {port} でサーバーを起動します")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
