"""Shopify Admin GraphQL integration."""
from __future__ import annotations

import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import load_settings

API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2027-01")


class ShopifyClient:
    def __init__(self) -> None:
        settings = load_settings()
        store = str(settings.get("shopify_store") or "").replace("https://", "").strip("/")
        token = str(settings.get("shopify_token") or "")
        if not store or not token:
            raise RuntimeError("未配置 Shopify 店铺域名或 Admin API Token")
        self.url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
        self.session = requests.Session()
        retries = Retry(total=4, backoff_factor=1.2, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.token = token

    def gql(self, query: str, variables: dict[str, Any] | None = None, attempts: int = 5) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self.session.post(
                    self.url,
                    headers={"X-Shopify-Access-Token": self.token, "Content-Type": "application/json"},
                    json={"query": query, "variables": variables or {}},
                    timeout=60,
                )
                response.raise_for_status()
                body = response.json()
                if body.get("errors"):
                    raise RuntimeError(str(body["errors"])[:500])
                return body.get("data") or {}
            except Exception as exc:
                last_error = exc
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Shopify 请求失败：{last_error}")

    def test(self) -> dict[str, Any]:
        data = self.gql("{ shop { name myshopifyDomain } }")
        return data.get("shop") or {}

    def find_by_sku(self, sku: str) -> dict[str, Any] | None:
        query = '{ products(first: 1, query: "sku:%s") { edges { node { id title handle status } } } }'
        data = self.gql(query % sku.replace('"', ""))
        edges = data.get("products", {}).get("edges", [])
        return edges[0]["node"] if edges else None

    def create_product(self, product: dict[str, Any]) -> dict[str, Any]:
        result = self.gql(
            """mutation Create($input: ProductInput!) {
              productCreate(input: $input) {
                product { id title handle status variants(first: 1) { edges { node { id inventoryItem { id } } } } }
                userErrors { field message }
              }
            }""",
            {
                "input": {
                    key: value
                    for key, value in {
                        "title": product["title"],
                        "descriptionHtml": product.get("description_html", ""),
                        "vendor": product.get("vendor", ""),
                        "productType": product.get("product_type", ""),
                        "tags": product.get("tags", []),
                        "status": "DRAFT",
                        "category": product.get("category") or None,
                        "seo": {
                            "title": product.get("seo_title") or product["title"],
                            "description": product.get("seo_description", ""),
                        },
                    }.items()
                    if value not in (None, "")
                }
            },
        )["productCreate"]
        if result.get("userErrors"):
            raise RuntimeError(str(result["userErrors"]))
        created = result["product"]
        variant = created["variants"]["edges"][0]["node"]
        synced = self.sync_variant(product, created["id"], variant["id"])
        media = []
        for image in product.get("images", [])[:20]:
            if image and Path(image).exists():
                try:
                    media.append(self.upload_image(created["id"], image, product["title"]))
                except Exception as exc:
                    media.append({"error": str(exc)[:160]})
        return {
            "product_id": created["id"],
            "variant_id": variant["id"],
            "handle": created["handle"],
            "status": "ACTIVE",
            "media": media,
            "inventory": synced.get("inventory"),
        }

    def sync_variant(self, product: dict[str, Any], product_id: str, variant_id: str) -> dict[str, Any]:
        result = self.gql(
            """mutation Update($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
              productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                productVariants { id sku price inventoryItem { id } }
                userErrors { field message }
              }
            }""",
            {
                "productId": product_id,
                "variants": [
                    {
                        "id": variant_id,
                        "price": str(product["price"]),
                        "compareAtPrice": str(product["compare_at_price"]) if product.get("compare_at_price") else None,
                        "inventoryPolicy": "DENY",
                        "inventoryItem": {
                            "sku": product["sku"],
                            "cost": str(product.get("cost", 0)),
                            "tracked": True,
                            "requiresShipping": True,
                            "measurement": {
                                "weight": {"value": float(product.get("weight_kg", 1.0)), "unit": "KILOGRAMS"},
                                "packedDimensions": {
                                    "length": float(product.get("packed_length", 35)),
                                    "width": float(product.get("packed_width", 25)),
                                    "height": float(product.get("packed_height", 8)),
                                    "unit": product.get("packed_unit", "CENTIMETERS"),
                                },
                            },
                        },
                    }
                ],
            },
        )["productVariantsBulkUpdate"]
        if result.get("userErrors"):
            raise RuntimeError(str(result["userErrors"]))
        item_id = result["productVariants"][0]["inventoryItem"]["id"]
        inventory = self.set_inventory(item_id, int(product.get("stock", 0)))
        self.gql(
            "mutation SetActive($product: ProductUpdateInput!) { productUpdate(product: $product) { product { id status } userErrors { field message } } }",
            {"product": {"id": product_id, "status": "ACTIVE"}},
        )
        return {"variant_id": variant_id, "inventory_item_id": item_id, "inventory": inventory}

    def set_inventory(self, inventory_item_id: str, target: int) -> dict[str, Any]:
        data = self.gql(
            """query Inventory($id: ID!) {
              inventoryItem(id: $id) {
                inventoryLevels(first: 10) { edges { node { location { id } quantities(names: ["available"]) { name quantity } } } }
              }
            }""",
            {"id": inventory_item_id},
        )
        edges = data.get("inventoryItem", {}).get("inventoryLevels", {}).get("edges", [])
        if not edges:
            return {"status": "skipped", "reason": "no_inventory_level"}
        level = edges[0]["node"]
        current = 0
        for quantity in level.get("quantities", []):
            if quantity.get("name") == "available":
                current = int(quantity.get("quantity") or 0)
        delta = target - current
        if delta == 0:
            return {"status": "unchanged", "available": current}
        result = self.gql(
            """mutation Adjust($input: InventoryAdjustQuantitiesInput!) {
              inventoryAdjustQuantities(input: $input) {
                userErrors { field message }
              }
            }""",
            {
                "input": {
                    "reason": "correction",
                    "name": "available",
                    "changes": [
                        {
                            "delta": delta,
                            "inventoryItemId": inventory_item_id,
                            "locationId": level["location"]["id"],
                            "changeFromQuantity": current,
                        }
                    ],
                }
            },
        )["inventoryAdjustQuantities"]
        if result.get("userErrors"):
            raise RuntimeError(str(result["userErrors"]))
        return {"status": "updated", "from": current, "to": target}

    def upload_image(self, product_id: str, image_path: str | Path, alt: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(path)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        staged = self.gql(
            """mutation Stage($input: [StagedUploadInput!]!) {
              stagedUploadsCreate(input: $input) {
                stagedTargets { url resourceUrl parameters { name value } }
                userErrors { field message }
              }
            }""",
            {
                "input": [
                    {
                        "filename": path.name,
                        "mimeType": mime,
                        "resource": "IMAGE",
                        "fileSize": str(path.stat().st_size),
                    }
                ]
            },
        )["stagedUploadsCreate"]
        if staged.get("userErrors"):
            raise RuntimeError(str(staged["userErrors"]))
        target = staged["stagedTargets"][0]
        with path.open("rb") as handle:
            upload = requests.put(
                target["url"],
                data=handle,
                headers={"Content-Type": mime},
                timeout=120,
            )
        upload.raise_for_status()
        media = self.gql(
            """mutation Media($productId: ID!, $media: [CreateMediaInput!]!) {
              productCreateMedia(productId: $productId, media: $media) {
                media { id alt mediaContentType status }
                mediaUserErrors { field message }
              }
            }""",
            {
                "productId": product_id,
                "media": [
                    {
                        "originalSource": target["resourceUrl"],
                        "alt": alt,
                        "mediaContentType": "IMAGE",
                    }
                ],
            },
        )["productCreateMedia"]
        if media.get("mediaUserErrors"):
            raise RuntimeError(str(media["mediaUserErrors"]))
        return media["media"][0]["id"]


    def update_price(self, product: dict[str, Any], new_price: float) -> dict[str, Any]:
        """Update only the Shopify variant price and keep the rest untouched."""
        existing = self.find_by_sku(product["sku"])
        if not existing:
            raise RuntimeError("Shopify 中不存在该 SKU")
        detail = self.gql(
            "query Product($id:ID!){product(id:$id){variants(first:1){edges{node{id price}}}}}",
            {"id": existing["id"]},
        )["product"]
        variant = detail["variants"]["edges"][0]["node"]
        compare_at = product.get("compare_at")
        result = self.gql(
            """mutation Price($productId:ID!,$variants:[ProductVariantsBulkInput!]!){
              productVariantsBulkUpdate(productId:$productId,variants:$variants){
                productVariants{id price compareAtPrice} userErrors{field message}
              }
            }""",
            {
                "productId": existing["id"],
                "variants": [{
                    "id": variant["id"],
                    "price": f"{float(new_price):.2f}",
                    "compareAtPrice": f"{float(compare_at):.2f}" if compare_at else None,
                }],
            },
        )["productVariantsBulkUpdate"]
        if result.get("userErrors"):
            raise RuntimeError(str(result["userErrors"]))
        updated = result["productVariants"][0]
        return {"product_id": existing["id"], "variant_id": updated["id"], "price": updated["price"]}

    def sync_product(self, product: dict[str, Any], new_image: str | None = None) -> dict[str, Any]:
        pid = product.get("shopify_id") or ""
        existing = self.find_by_sku(product["sku"])
        if existing:
            pid = existing["id"]
        if not pid:
            return self.create_product({**product, "images": ([new_image] if new_image else product.get("images", []))})

        detail = self.gql(
            """query Product($id: ID!) {
              product(id: $id) {
                id handle status
                variants(first: 1) { edges { node { id price inventoryItem { id } } } }
              }
            }""",
            {"id": pid},
        )["product"]
        variant = detail["variants"]["edges"][0]["node"]
        synced = self.sync_variant(product, pid, variant["id"])
        media: list[Any] = []
        if new_image and Path(new_image).exists():
            media.append(self.upload_image(pid, new_image, product["title"]))
        return {
            "product_id": pid,
            "variant_id": variant["id"],
            "handle": detail["handle"],
            "status": "ACTIVE",
            "media": media,
            "inventory": synced.get("inventory"),
            "existing": True,
        }

