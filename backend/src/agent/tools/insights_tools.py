"""
LangChain tools for Market Insights Platform.
Enables the LLM agent to query and explain market insight categories and metrics.
"""

import structlog
from langchain_core.tools import tool

from ...services.insights import InsightsCategoryRegistry

logger = structlog.get_logger()


def create_insights_tools(
    registry: InsightsCategoryRegistry,
) -> list:
    """
    Create Market Insights tools for the LLM agent.

    These tools allow the agent to:
    1. List available insight categories
    2. Get detailed metrics for a category
    3. Get individual metric explanations

    Args:
        registry: InsightsCategoryRegistry instance with dependencies

    Returns:
        List of LangChain tools
    """

    @tool
    async def list_insight_categories() -> str:
        """
        List all available market insight categories.

        Returns the names and descriptions of insight categories
        that can be queried for detailed metrics and analysis.

        Use this when the user asks about what insights are available
        or wants an overview of market analysis capabilities.

        Returns:
            List of categories with names, icons, and descriptions
        """
        try:
            categories = registry.list_categories()

            if not categories:
                return "No insight categories are currently available."

            lines = ["## Available Market Insight Categories\n"]
            for cat in categories:
                lines.append(f"**{cat.icon} {cat.name}** (`{cat.id}`)")
                lines.append(f"  {cat.description}")
                lines.append(f"  Metrics: {cat.metric_count}\n")

            return "\n".join(lines)

        except Exception as e:
            logger.error("Failed to list insight categories", error=str(e))
            return f"Error listing insight categories: {str(e)}"

    @tool
    async def get_insight_category(category_id: str) -> str:
        """
        Get detailed metrics and composite score for a market insight category.

        This tool provides comprehensive analysis including:
        - Composite score (0-100) with interpretation
        - Individual metric scores with status levels
        - Actionable insights for each metric

        Args:
            category_id: Category identifier (e.g., "ai_sector_risk")
                        Use list_insight_categories to see available categories.

        Returns:
            Formatted analysis with scores, status, and recommendations

        Example:
            get_insight_category("ai_sector_risk")
        """
        try:
            data = await registry.get_category_data(category_id)

            if data is None:
                available = [c.id for c in registry.list_categories()]
                return (
                    f"Category '{category_id}' not found. "
                    f"Available categories: {', '.join(available)}"
                )

            lines = [f"## {data.icon} {data.name}\n"]

            # Composite score
            if data.composite:
                lines.append("### Overall Assessment")
                lines.append(
                    f"**Composite Score: {data.composite.score:.0f}/100** "
                    f"({data.composite.status.upper()})"
                )
                lines.append(f"\n{data.composite.interpretation}\n")

            # Individual metrics
            lines.append("### Metrics\n")
            for metric in data.metrics:
                status_emoji = _get_status_emoji(metric.status.value)
                lines.append(
                    f"{status_emoji} **{metric.name}**: "
                    f"{metric.score:.0f}/100 ({metric.status.value})"
                )
                lines.append(f"   {metric.explanation.summary}")
                lines.append(f"   💡 *{metric.explanation.actionable_insight}*\n")

            # Data timestamp
            lines.append(f"\n---\n*Last updated: {data.last_updated.isoformat()}*")

            return "\n".join(lines)

        except Exception as e:
            logger.error(
                "Failed to get insight category",
                category_id=category_id,
                error=str(e),
            )
            return f"Error retrieving category '{category_id}': {str(e)}"

    @tool
    async def get_insight_metric(category_id: str, metric_id: str) -> str:
        """
        Get detailed explanation for a specific market insight metric.

        Provides in-depth analysis including:
        - Score with historical context
        - Methodology explanation
        - Calculation formula (if applicable)
        - Actionable recommendations
        - Data sources used

        Args:
            category_id: Category identifier (e.g., "ai_sector_risk")
            metric_id: Metric identifier within the category
                      (e.g., "ai_price_anomaly", "news_sentiment")

        Returns:
            Rich explanation with methodology and recommendations

        Example:
            get_insight_metric("ai_sector_risk", "ai_price_anomaly")
        """
        try:
            instance = registry.get_category_instance(category_id)

            if instance is None:
                available = [c.id for c in registry.list_categories()]
                return (
                    f"Category '{category_id}' not found. "
                    f"Available: {', '.join(available)}"
                )

            metric = await instance.get_metric(metric_id)

            if metric is None:
                # List available metrics
                data = await instance.get_category_data()
                available_metrics = [m.id for m in data.metrics]
                return (
                    f"Metric '{metric_id}' not found in category '{category_id}'. "
                    f"Available metrics: {', '.join(available_metrics)}"
                )

            status_emoji = _get_status_emoji(metric.status.value)
            lines = [
                f"## {metric.name} {status_emoji}",
                f"**Score: {metric.score:.0f}/100** | Status: {metric.status.value.upper()}\n",
                f"### Summary\n{metric.explanation.summary}\n",
                f"### Detailed Analysis\n{metric.explanation.detail}\n",
                f"### Methodology\n{metric.explanation.methodology}",
            ]

            if metric.explanation.formula:
                lines.append(f"\n**Formula**: `{metric.explanation.formula}`")

            lines.extend(
                [
                    f"\n### Historical Context\n{metric.explanation.historical_context}\n",
                    f"### What This Means For You\n💡 {metric.explanation.actionable_insight}\n",
                    "### Data Sources\n" + ", ".join(metric.data_sources),
                    f"\n---\n*Last updated: {metric.last_updated.isoformat()}*",
                ]
            )

            return "\n".join(lines)

        except Exception as e:
            logger.error(
                "Failed to get insight metric",
                category_id=category_id,
                metric_id=metric_id,
                error=str(e),
            )
            return (
                f"Error retrieving metric '{metric_id}' "
                f"from category '{category_id}': {str(e)}"
            )

    return [list_insight_categories, get_insight_category, get_insight_metric]


def _get_status_emoji(status: str) -> str:
    """Get emoji for metric status level."""
    return {
        "low": "🟢",
        "normal": "🔵",
        "elevated": "🟠",
        "high": "🔴",
    }.get(status, "⚪")
