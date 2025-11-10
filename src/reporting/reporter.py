"""
Reporting module for portfolio and trade reporting.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class Reporter:
    """Handles reporting for portfolio and trades."""

    def __init__(self, storage, portfolio_manager, position_manager):
        """
        Initialize reporter.

        Args:
            storage: DatabaseStorage instance
            portfolio_manager: PortfolioManager instance
            position_manager: PositionManager instance
        """
        self.storage = storage
        self.portfolio = portfolio_manager
        self.positions = position_manager

    def report_portfolio_status(self):
        """Generate and log current portfolio status."""
        # Get positions summary
        positions_summary = self.positions.get_position_summary()
        positions_value = positions_summary['total_value']
        num_positions = positions_summary['count']

        # Get portfolio summary
        portfolio_summary = self.portfolio.get_portfolio_summary(positions_value, num_positions)

        # Create report
        report_lines = [
            "",
            "=" * 80,
            "📊 PORTFOLIO STATUS",
            "=" * 80,
            f"Total Value:        ${portfolio_summary['total_value']:>12,.2f}",
            f"Cash (Liquidity):   ${portfolio_summary['cash']:>12,.2f} ({portfolio_summary['cash_percentage']:>5.1f}%)",
            f"Positions Value:    ${portfolio_summary['positions_value']:>12,.2f} ({portfolio_summary['positions_percentage']:>5.1f}%)",
            f"Open Positions:     {portfolio_summary['num_positions']:>12}",
            "",
            f"Initial Balance:    ${portfolio_summary['initial_balance']:>12,.2f}",
            f"Total Return:       ${portfolio_summary['total_return']:>12,.2f} ({portfolio_summary['total_return_percentage']:>+6.2f}%)",
            "=" * 80
        ]

        # Log to console
        for line in report_lines:
            logger.info(line)

        return portfolio_summary

    def report_positions(self):
        """Generate and log detailed positions report."""
        positions_summary = self.positions.get_position_summary()

        if positions_summary['count'] == 0:
            logger.info("No open positions")
            return

        report_lines = [
            "",
            "=" * 100,
            "📈 OPEN POSITIONS",
            "=" * 100,
            f"{'Asset':<10} {'Units':>12} {'Entry':>12} {'Current':>12} {'Value':>12} {'P&L':>12} {'P&L %':>8} {'Days':>6}",
            "-" * 100
        ]

        for pos in positions_summary['positions']:
            # Calculate days in position
            days_in_position = (datetime.now() - pos['entry_time']).days

            report_lines.append(
                f"{pos['asset']:<10} "
                f"{pos['units']:>12.6f} "
                f"${pos['entry_price']:>11.4f} "
                f"${pos['current_price']:>11.4f} "
                f"${pos['current_value']:>11.2f} "
                f"${pos['unrealized_pnl']:>11.2f} "
                f"{pos['unrealized_pnl_pct']:>+7.2f}% "
                f"{days_in_position:>6}"
            )

        report_lines.extend([
            "-" * 100,
            f"{'TOTAL':<10} {'':<12} {'':<12} {'':<12} "
            f"${positions_summary['total_value']:>11.2f} "
            f"${positions_summary['total_unrealized_pnl']:>11.2f} {'':<8} {'':<6}",
            "=" * 100
        ])

        for line in report_lines:
            logger.info(line)

    def report_daily_summary(self, timestamp: datetime):
        """
        Generate daily summary report.

        Args:
            timestamp: Report timestamp
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📅 DAILY SUMMARY - {timestamp.strftime('%Y-%m-%d')}")
        logger.info("=" * 80)

        # Portfolio status
        self.report_portfolio_status()

        # Positions
        self.report_positions()

        # Recent trades
        self.report_recent_trades(limit=10)

        # Trading statistics
        self.report_trading_statistics()

        logger.info("=" * 80)
        logger.info("")

    def report_recent_trades(self, limit: int = 10):
        """
        Report recent trades.

        Args:
            limit: Number of recent trades to show
        """
        trades = self.storage.get_all_trades(limit=limit)

        if not trades:
            logger.info("No trades executed yet")
            return

        report_lines = [
            "",
            f"🔄 RECENT TRADES (Last {min(limit, len(trades))})",
            "-" * 120,
            f"{'Type':<6} {'Asset':<10} {'Time':<20} {'Price':>12} {'Units':>12} {'Value':>12} {'Fee':>10} {'P&L':>12} {'P&L %':>8}",
            "-" * 120
        ]

        for trade in trades:
            time_str = trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            pnl_str = f"${trade.get('profit_loss', 0):>11.2f}" if trade['trade_type'] == 'EXIT' else ' ' * 12
            pnl_pct_str = f"{trade.get('profit_loss_percentage', 0):>+7.2f}%" if trade['trade_type'] == 'EXIT' else ' ' * 8

            report_lines.append(
                f"{trade['trade_type']:<6} "
                f"{trade['asset']:<10} "
                f"{time_str:<20} "
                f"${float(trade['price']):>11.4f} "
                f"{float(trade['units']):>12.6f} "
                f"${float(trade['value']):>11.2f} "
                f"${float(trade['fee']):>9.2f} "
                f"{pnl_str} "
                f"{pnl_pct_str}"
            )

        report_lines.append("-" * 120)

        for line in report_lines:
            logger.info(line)

    def report_trading_statistics(self):
        """Report overall trading statistics."""
        all_trades = self.storage.get_all_trades()

        if not all_trades:
            logger.info("No trading statistics available yet")
            return

        entries = [t for t in all_trades if t['trade_type'] == 'ENTRY']
        exits = [t for t in all_trades if t['trade_type'] == 'EXIT']

        total_fees = sum(float(t['fee']) for t in all_trades)

        # Calculate P&L statistics
        if exits:
            exit_pnls = [float(t.get('profit_loss', 0)) for t in exits if t.get('profit_loss') is not None]
            winning_trades = [pnl for pnl in exit_pnls if pnl > 0]
            losing_trades = [pnl for pnl in exit_pnls if pnl <= 0]

            total_pnl = sum(exit_pnls)
            avg_pnl = total_pnl / len(exits) if exits else 0
            win_rate = len(winning_trades) / len(exits) * 100 if exits else 0

            avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0

            # Calculate average time in trade
            times_in_trade = [float(t.get('time_in_trade_hours', 0)) for t in exits if t.get('time_in_trade_hours')]
            avg_time = sum(times_in_trade) / len(times_in_trade) if times_in_trade else 0
        else:
            total_pnl = 0
            avg_pnl = 0
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            avg_time = 0
            winning_trades = []
            losing_trades = []

        report_lines = [
            "",
            "📊 TRADING STATISTICS",
            "-" * 80,
            f"Total Trades:       {len(all_trades):>12} (Entries: {len(entries)}, Exits: {len(exits)})",
            f"Total Fees Paid:    ${total_fees:>12,.2f}",
            "",
            f"Closed Trades:      {len(exits):>12}",
            f"Winning Trades:     {len(winning_trades):>12} ({win_rate:.1f}%)",
            f"Losing Trades:      {len(losing_trades):>12}",
            "",
            f"Total P&L:          ${total_pnl:>12,.2f}",
            f"Average P&L:        ${avg_pnl:>12,.2f}",
            f"Average Win:        ${avg_win:>12,.2f}",
            f"Average Loss:       ${avg_loss:>12,.2f}",
            f"Avg Time in Trade:  {avg_time:>12.1f} hours",
            "-" * 80
        ]

        for line in report_lines:
            logger.info(line)

    def generate_performance_metrics(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance metrics.

        Returns:
            Dictionary with performance metrics
        """
        # Get portfolio data
        positions_summary = self.positions.get_position_summary()
        portfolio_summary = self.portfolio.get_portfolio_summary(
            positions_summary['total_value'],
            positions_summary['count']
        )

        # Get trading statistics
        all_trades = self.storage.get_all_trades()
        exits = [t for t in all_trades if t['trade_type'] == 'EXIT']

        # Calculate metrics
        if exits:
            exit_pnls = [float(t.get('profit_loss', 0)) for t in exits if t.get('profit_loss') is not None]
            winning_trades = [pnl for pnl in exit_pnls if pnl > 0]
            losing_trades = [pnl for pnl in exit_pnls if pnl <= 0]

            total_pnl = sum(exit_pnls)
            win_rate = len(winning_trades) / len(exits) * 100 if exits else 0
        else:
            total_pnl = 0
            win_rate = 0
            winning_trades = []
            losing_trades = []

        return {
            'portfolio': portfolio_summary,
            'positions': positions_summary,
            'trades': {
                'total': len(all_trades),
                'closed': len(exits),
                'winning': len(winning_trades),
                'losing': len(losing_trades),
                'win_rate': win_rate,
                'total_pnl': total_pnl
            }
        }
