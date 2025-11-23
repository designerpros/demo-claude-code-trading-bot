#!/usr/bin/env python3
"""
Run backtest on historical data.

Usage:
    python run_backtest.py --start 2021-01-01 --end 2022-05-01
    python run_backtest.py --preset altseason-2021
"""

import argparse
import yaml
import sys
from pathlib import Path
from datetime import date
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from backtesting.backtester import Backtester


# Predefined backtest periods
PRESETS = {
    'altseason-2021': {
        'start': date(2021, 1, 1),
        'end': date(2022, 5, 1),
        'description': '2021-2022 Altseason (Jan 2021 - May 2022)'
    },
    'bull-market-2021': {
        'start': date(2021, 1, 1),
        'end': date(2021, 11, 30),
        'description': '2021 Bull Market Peak (Jan - Nov 2021)'
    },
    'bear-market-2022': {
        'start': date(2022, 1, 1),
        'end': date(2022, 12, 31),
        'description': '2022 Bear Market (Full Year)'
    },
    'recent-year': {
        'start': date(2023, 1, 1),
        'end': date(2024, 1, 1),
        'description': '2023 Full Year'
    }
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run strategy backtest on historical data')

    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--preset',
        type=str,
        choices=list(PRESETS.keys()),
        help='Use predefined backtest period'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to config file'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for detailed results (JSON)'
    )
    parser.add_argument(
        '--list-presets',
        action='store_true',
        help='List available preset periods'
    )

    return parser.parse_args()


def list_presets():
    """Print available preset periods."""
    print("\n📅 Available Backtest Presets:\n")
    for name, info in PRESETS.items():
        print(f"  {name:20s} : {info['description']}")
        print(f"  {'':20s}   {info['start']} to {info['end']}\n")


def main():
    """Run backtest."""
    args = parse_args()

    # List presets if requested
    if args.list_presets:
        list_presets()
        return

    # Determine start and end dates
    if args.preset:
        preset = PRESETS[args.preset]
        start_date = preset['start']
        end_date = preset['end']
        print(f"\n🎯 Using preset: {preset['description']}")
    elif args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
    else:
        print("❌ Error: Must specify either --preset or both --start and --end")
        print("   Use --list-presets to see available presets")
        return

    # Load configuration
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    print(f"\n📊 Running backtest: {start_date} to {end_date}")
    print(f"⚙️  Configuration: {args.config}\n")

    # Create and run backtester
    backtester = Backtester(config)
    results = backtester.run_backtest(start_date, end_date)

    if not results:
        print("❌ Backtest failed - no results generated")
        return

    # Print results
    backtester.print_results(results)

    # Save detailed results if output file specified
    if args.output:
        # Convert non-serializable objects
        output_data = {
            'period': {
                'start': str(results['start_date']),
                'end': str(results['end_date']),
                'days': results['days']
            },
            'performance': {
                'initial_balance': results['initial_balance'],
                'final_balance': results['final_balance'],
                'total_return': results['total_return'],
                'total_pnl': results['total_pnl']
            },
            'statistics': {
                'total_trades': results['total_trades'],
                'winners': results['winners'],
                'losers': results['losers'],
                'win_rate': results['win_rate'],
                'avg_win_pct': results['avg_win_pct'],
                'avg_loss_pct': results['avg_loss_pct'],
                'best_trade_pct': results['best_trade_pct'],
                'worst_trade_pct': results['worst_trade_pct']
            },
            'risk_metrics': {
                'max_drawdown': results['max_drawdown'],
                'sharpe_ratio': results['sharpe_ratio']
            },
            'exit_reasons': results['exit_reasons'],
            'equity_curve': results['equity_curve'],
            'trades': [
                {
                    'asset': t.asset,
                    'entry_date': str(t.entry_date),
                    'entry_price': t.entry_price,
                    'exit_date': str(t.exit_date),
                    'exit_price': t.exit_price,
                    'pnl': t.pnl,
                    'pnl_pct': t.pnl_pct,
                    'exit_reason': t.exit_reason
                }
                for t in results['closed_trades']
            ]
        }

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n💾 Detailed results saved to: {args.output}")

    # Summary
    print("\n✅ Backtest complete!")


if __name__ == '__main__':
    main()
