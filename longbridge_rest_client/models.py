"""Typed request and response field catalog for the Longbridge REST API.

The REST specification currently omits formal schemas for several successful
responses.  The models below preserve the documented example fields while the
client still returns the original JSON payload without lossy transformation.
Every field comment is intentionally written in English for IDE/tooling use.
"""

from __future__ import annotations

from typing import Any, List, TypedDict


class APIEnvelope(TypedDict, total=False):
    code: int  # Application response code; zero means success.
    message: str  # Human-readable application response message.
    data: Any  # Endpoint-specific response payload.


class ErrorResponse(TypedDict, total=False):
    code: int  # Longbridge error code.
    message: str  # Human-readable error message.
    data: Any  # Optional error details returned by the gateway.


class CreateWatchlistGroupRequest(TypedDict, total=False):
    name: str  # New watchlist group name.
    securities: List[str]  # Optional symbols to add when creating the group.


class UpdateWatchlistGroupRequest(TypedDict, total=False):
    id: str  # Watchlist group identifier to update.
    name: str  # Replacement watchlist group name.
    mode: str  # Security update mode: add, remove, or replace.
    securities: List[str]  # Symbols affected by the selected update mode.


class CreateTopicRequest(TypedDict, total=False):
    title: str  # Topic title; required for article topics.
    body: str  # Topic body; plain text for posts and Markdown for articles.
    topic_type: str  # Topic type: article or post.
    tickers: List[str]  # Associated security symbols, with a maximum of ten.
    hashtags: List[str]  # Associated hashtag names, with a maximum of one.


class CreateTopicReplyRequest(TypedDict, total=False):
    body: str  # Plain-text reply body.
    reply_to_id: str  # Optional parent comment identifier; zero means top-level.


class ReplaceOrderRequest(TypedDict, total=False):
    order_id: str  # Existing order identifier to modify.
    quantity: str  # Replacement order quantity.
    price: str  # Replacement limit price.
    trigger_price: str  # Replacement trigger price for MIT/LIT orders.
    limit_offset: str  # Replacement limit offset for LIT orders.
    trailing_amount: str  # Replacement trailing amount for trailing orders.
    trailing_percent: str  # Replacement trailing percentage for trailing orders.
    limit_depth_level: int  # Replacement depth level for ELO orders.
    trigger_count: int  # Replacement trigger count.
    monitor_price: str  # Replacement monitored price.
    remark: str  # Replacement order remark, limited to 255 characters.


class WatchlistSecurity(TypedDict, total=False):
    symbol: str  # Security symbol in ticker.region format.
    market: str  # Security market code.
    name: str  # Display name of the security.
    watched_price: str  # Price recorded when the security was added.
    watched_at: str  # Unix timestamp when the security was added.
    is_pinned: bool  # Whether the security is pinned in the group.


class WatchlistGroup(TypedDict, total=False):
    id: str  # Watchlist group identifier.
    name: str  # Watchlist group display name.
    securities: List[WatchlistSecurity]  # Securities contained in the group.


class WatchlistGroupsData(TypedDict, total=False):
    groups: List[WatchlistGroup]  # Watchlist groups owned by the current user.


class WatchlistGroupIDData(TypedDict, total=False):
    id: str  # Identifier of the newly created watchlist group.


class EmptyData(TypedDict, total=False):
    """Empty success payload used by update and delete operations."""


class SecurityListItem(TypedDict, total=False):
    symbol: str  # Tradable security symbol.
    name_cn: str  # Simplified Chinese security name.
    name_hk: str  # Traditional Chinese security name.
    name_en: str  # English security name.


class SecurityListData(TypedDict, total=False):
    list: List[SecurityListItem]  # Securities matching the market/category filter.


class MarketTemperaturePoint(TypedDict, total=False):
    timestamp: str  # Unix timestamp of the daily observation.
    temperature: int  # Overall market temperature score from 0 to 100.
    valuation: int  # Valuation sub-score from 0 to 100.
    sentiment: int  # Sentiment sub-score from 0 to 100.


class HistoricalMarketTemperatureData(TypedDict, total=False):
    list: List[MarketTemperaturePoint]  # Historical market temperature points.
    type: str  # Sampling period type, normally day.


class MarketTemperatureData(TypedDict, total=False):
    temperature: int  # Current market temperature score from 0 to 100.
    description: str  # Human-readable interpretation of the temperature.
    valuation: int  # Current valuation sub-score from 0 to 100.
    sentiment: int  # Current sentiment sub-score from 0 to 100.
    updated_at: str  # Unix timestamp of the latest update.


class CashFlowItem(TypedDict, total=False):
    transaction_flow_name: str  # Human-readable cash-flow business name.
    direction: int  # Cash-flow direction code.
    business_type: int  # Cash-flow business type code.
    balance: str  # Cash-flow amount represented as a decimal string.
    currency: str  # Currency of the cash-flow amount.
    business_time: str  # Unix timestamp of the business event.
    symbol: str  # Optional related security symbol.
    description: str  # Human-readable cash-flow description.


class CashFlowData(TypedDict, total=False):
    list: List[CashFlowItem]  # Cash-flow records matching the query.


class CashInfo(TypedDict, total=False):
    currency: str  # Currency represented by this cash bucket.
    withdraw_cash: str  # Cash currently available for withdrawal.
    available_cash: str  # Cash available for new transactions.
    frozen_cash: str  # Cash frozen by pending transactions.
    settling_cash: str  # Cash pending settlement.
    redemption_cash: str  # Cash pending fund redemption.


class AccountCashItem(TypedDict, total=False):
    total_cash: str  # Total cash for the account and currency.
    max_finance_amount: str  # Maximum financing amount.
    remaining_finance_amount: str  # Remaining financing amount.
    risk_level: str  # Account risk level code.
    margin_call: str  # Margin-call status code.
    currency: str  # Primary currency of this account cash record.
    net_assets: str  # Net asset value.
    init_margin: str  # Initial margin requirement.
    maintenance_margin: str  # Maintenance margin requirement.
    buy_power: str  # Available buying power.
    frozen_transaction_fees: List[Any]  # Frozen transaction fee details.
    cash_infos: List[CashInfo]  # Per-currency cash breakdown.


class AccountCashData(TypedDict, total=False):
    list: List[AccountCashItem]  # Account cash records.


class StockPosition(TypedDict, total=False):
    symbol: str  # Held security symbol.
    symbol_name: str  # Display name of the held security.
    currency: str  # Position currency.
    quantity: str  # Total held quantity.
    available_quantity: str  # Quantity available to sell.
    cost_price: str  # Average cost price.
    market: str  # Security market code.
    init_quantity: str  # Opening quantity for the position period.


class StockAccount(TypedDict, total=False):
    account_channel: str  # Sub-account or broker channel identifier.
    stock_info: List[StockPosition]  # Stock positions in this channel.


class StockPositionData(TypedDict, total=False):
    list: List[StockAccount]  # Stock positions grouped by account channel.


class FundPosition(TypedDict, total=False):
    symbol: str  # Fund symbol.
    symbol_name: str  # Display name of the fund.
    holding_units: str  # Number of fund units held.
    current_net_asset_value: str  # Current net asset value per unit.
    cost_net_asset_value: str  # Cost net asset value per unit.
    net_asset_value_day: str  # Unix timestamp of the net asset value date.
    currency: str  # Fund currency.


class FundAccount(TypedDict, total=False):
    fund_info: List[FundPosition]  # Fund positions in an account channel.


class FundPositionData(TypedDict, total=False):
    list: List[FundAccount]  # Fund positions grouped by account channel.


class StatementItem(TypedDict, total=False):
    date: str  # Statement date, for example 20260327.
    file_key: str  # File key used to request a download URL.


class StatementDownloadData(TypedDict, total=False):
    url: str  # Presigned URL used to download the statement JSON.


class FilingItem(TypedDict, total=False):
    id: str  # Filing identifier.
    title: str  # Filing title.
    description: str  # Filing description.
    file_name: str  # Original filing file name.
    file_urls: List[str]  # URLs of the filing files.
    publish_at: str  # Unix timestamp when the filing was published.


class FilingsData(TypedDict, total=False):
    items: List[FilingItem]  # Filings matching the requested symbol.


class NewsItem(TypedDict, total=False):
    id: str  # News article identifier.
    title: str  # News article title.
    description: str  # News article summary.
    url: str  # Public URL of the news article.
    published_at: str  # Unix timestamp when the article was published.
    comments_count: int  # Number of comments on the article.
    likes_count: int  # Number of likes on the article.
    shares_count: int  # Number of shares of the article.


class TopicSummary(TypedDict, total=False):
    id: str  # Community topic identifier.
    title: str  # Topic title, empty for some short posts.
    description: str  # Topic summary or short-post body.
    url: str  # Public URL of the topic.
    published_at: str  # Unix timestamp when the topic was published.
    comments_count: int  # Number of comments on the topic.
    likes_count: int  # Number of likes on the topic.
    shares_count: int  # Number of shares of the topic.


class TopicAuthor(TypedDict, total=False):
    member_id: str  # Community member identifier.
    name: str  # Display name of the author.
    avatar: str  # URL of the author avatar.


class TopicImage(TypedDict, total=False):
    url: str  # Original image URL.
    sm: str  # Small image URL.
    lg: str  # Large image URL.


class TopicItem(TypedDict, total=False):
    id: str  # Community topic identifier.
    title: str  # Topic title.
    description: str  # Topic summary.
    body: str  # Full topic body.
    topic_type: str  # Topic type: article or post.
    tickers: List[str]  # Security symbols associated with the topic.
    hashtags: List[str]  # Hashtags associated with the topic.
    images: List[TopicImage]  # Images attached to the topic.
    likes_count: int  # Number of likes.
    comments_count: int  # Number of comments.
    views_count: int  # Number of views.
    shares_count: int  # Number of shares.
    detail_url: str  # Public URL of the topic detail page.
    author: TopicAuthor  # Topic author information.
    license: int  # Content license code, when returned for owned topics.
    created_at: str  # Unix timestamp when the topic was created.
    updated_at: str  # Unix timestamp when the topic was last updated.


class TopicComment(TypedDict, total=False):
    id: str  # Comment identifier.
    topic_id: str  # Parent topic identifier.
    body: str  # Plain-text comment body.
    reply_to_id: str  # Parent comment identifier, or zero for top-level.
    author: TopicAuthor  # Comment author information.
    images: List[TopicImage]  # Images attached to the comment.
    likes_count: int  # Number of comment likes.
    comments_count: int  # Number of nested replies.
    created_at: str  # Unix timestamp when the comment was created.


class NewsData(TypedDict, total=False):
    items: List[NewsItem]  # News articles matching the symbol.


class TopicListData(TypedDict, total=False):
    items: List[TopicSummary]  # Community topics matching the symbol.


class MyTopicsData(TypedDict, total=False):
    items: List[TopicItem]  # Topics published by the current user.


class TopicItemData(TypedDict, total=False):
    item: TopicItem  # Topic detail or newly created topic.


class TopicCommentsData(TypedDict, total=False):
    items: List[TopicComment]  # Comments associated with the topic.


class TradeItem(TypedDict, total=False):
    trade_id: str  # Execution identifier.
    order_id: str  # Related order identifier.
    symbol: str  # Executed security symbol.
    price: str  # Execution price.
    quantity: str  # Executed quantity.
    trade_done_at: str  # Unix timestamp when the execution completed.


class HistoryExecutionsData(TypedDict, total=False):
    trades: List[TradeItem]  # Historical executions matching the filters.
    has_more: bool  # Whether another page of executions is available.


class ChargeItem(TypedDict, total=False):
    code: str  # Fee category code.
    name: str  # Human-readable fee category name.
    fees: List[Any]  # Individual fee entries in the category.


class ChargeDetail(TypedDict, total=False):
    items: List[ChargeItem]  # Fee categories for the order.
    total_amount: str  # Total fee amount.
    currency: str  # Currency of the total fee amount.


class OrderItem(TypedDict, total=False):
    order_id: str  # Order identifier.
    status: str  # Current order status.
    stock_name: str  # Display name of the security.
    quantity: str  # Requested order quantity.
    executed_quantity: str  # Executed order quantity.
    price: str  # Requested order price.
    executed_price: str  # Average executed price.
    submitted_at: str  # Unix timestamp when the order was submitted.
    side: str  # Order side, such as Buy or Sell.
    symbol: str  # Ordered security symbol.
    order_type: str  # Order type code.
    last_done: str  # Latest execution price.
    trigger_price: str  # Trigger price for conditional orders.
    msg: str  # Broker or gateway message.
    tag: str  # Order tag.
    time_in_force: str  # Time-in-force policy.
    expire_date: str  # Order expiry date.
    updated_at: str  # Unix timestamp of the latest order update.
    trigger_at: str  # Unix timestamp when the order was triggered.
    trailing_amount: str  # Trailing amount for trailing orders.
    trailing_percent: str  # Trailing percentage for trailing orders.
    limit_offset: str  # Limit offset for LIT orders.
    trigger_status: str  # Conditional-order trigger status.
    outside_rth: str  # Outside-regular-trading-hours policy.
    currency: str  # Settlement currency.
    remark: str  # User-provided order remark.
    limit_depth_level: int  # Depth level for enhanced limit orders.
    trigger_count: int  # Number of trigger events.
    monitor_price: str  # Current monitored price.
    free_status: str  # Free-share status code.
    free_amount: str  # Free-share amount.
    free_currency: str  # Free-share currency.
    deductions_status: str  # Deduction status code.
    deductions_amount: str  # Deduction amount.
    deductions_currency: str  # Deduction currency.
    platform_deducted_status: str  # Platform deduction status code.
    platform_deducted_amount: str  # Platform deduction amount.
    platform_deducted_currency: str  # Platform deduction currency.
    history: List[Any]  # Order history events.
    charge_detail: ChargeDetail  # Order fee breakdown.


class HistoryOrdersData(TypedDict, total=False):
    orders: List[OrderItem]  # Historical orders matching the filters.
    has_more: bool  # Whether another page of orders is available.


class OrderDetailData(TypedDict, total=False):
    order_id: str  # Order identifier.
    status: str  # Current order status.
    stock_name: str  # Display name of the security.
    quantity: str  # Requested order quantity.
    executed_quantity: str  # Executed order quantity.
    price: str  # Requested order price.
    executed_price: str  # Average executed price.
    submitted_at: str  # Unix timestamp when the order was submitted.
    side: str  # Order side.
    symbol: str  # Ordered security symbol.
    order_type: str  # Order type code.
    last_done: str  # Latest execution price.
    trigger_price: str  # Trigger price for conditional orders.
    msg: str  # Broker or gateway message.
    tag: str  # Order tag.
    time_in_force: str  # Time-in-force policy.
    expire_date: str  # Order expiry date.
    updated_at: str  # Unix timestamp of the latest order update.
    trigger_at: str  # Unix timestamp when the order was triggered.
    trailing_amount: str  # Trailing amount for trailing orders.
    trailing_percent: str  # Trailing percentage for trailing orders.
    limit_offset: str  # Limit offset for LIT orders.
    trigger_status: str  # Conditional-order trigger status.
    outside_rth: str  # Outside-regular-trading-hours policy.
    currency: str  # Settlement currency.
    remark: str  # User-provided order remark.
    limit_depth_level: int  # Depth level for enhanced limit orders.
    trigger_count: int  # Number of trigger events.
    monitor_price: str  # Current monitored price.
    free_status: str  # Free-share status code.
    free_amount: str  # Free-share amount.
    free_currency: str  # Free-share currency.
    deductions_status: str  # Deduction status code.
    deductions_amount: str  # Deduction amount.
    deductions_currency: str  # Deduction currency.
    platform_deducted_status: str  # Platform deduction status code.
    platform_deducted_amount: str  # Platform deduction amount.
    platform_deducted_currency: str  # Platform deduction currency.
    history: List[Any]  # Order history events.
    charge_detail: ChargeDetail  # Order fee breakdown.


class BuyLimitData(TypedDict, total=False):
    cash_max_qty: str  # Maximum quantity purchasable with cash.
    margin_max_qty: str  # Maximum quantity purchasable with margin.
