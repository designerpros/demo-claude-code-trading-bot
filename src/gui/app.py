"""
Flask web application for trading bot GUI dashboard.
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import yaml
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.storage import DatabaseStorage
from portfolio.manager import PortfolioManager
from strategy.position_manager import PositionManager

app = Flask(__name__)
CORS(app)

# Load configuration (path relative to project root)
project_root = Path(__file__).parent.parent.parent
config_path = project_root / 'config' / 'config.yaml'

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Initialize components
storage = DatabaseStorage(config['database'])
portfolio = PortfolioManager(storage, config['portfolio']['initial_balance'])
positions = PositionManager(storage)

# Load portfolio from latest snapshot
portfolio.initialize_from_snapshot()


@app.route('/')
def index():
    """Render main dashboard."""
    return render_template('dashboard.html',
                         refresh_interval=config['gui']['refresh_interval_seconds'])


@app.route('/api/portfolio')
def get_portfolio():
    """Get portfolio summary data."""
    try:
        # Refresh positions
        positions.refresh_positions()

        # Get positions summary
        positions_summary = positions.get_position_summary()

        # Get portfolio summary
        portfolio_summary = portfolio.get_portfolio_summary(
            positions_summary['total_value'],
            positions_summary['count']
        )

        return jsonify({
            'success': True,
            'data': portfolio_summary,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/positions')
def get_positions():
    """Get open positions data."""
    try:
        positions.refresh_positions()
        positions_summary = positions.get_position_summary()

        # Format positions for display
        formatted_positions = []
        for pos in positions_summary['positions']:
            formatted_positions.append({
                'asset': pos['asset'],
                'units': f"{pos['units']:.6f}",
                'entry_price': f"{pos['entry_price']:.4f}",
                'current_price': f"{pos['current_price']:.4f}",
                'current_value': f"{pos['current_value']:.2f}",
                'unrealized_pnl': f"{pos['unrealized_pnl']:.2f}",
                'unrealized_pnl_pct': f"{pos['unrealized_pnl_pct']:.2f}",
                'entry_time': pos['entry_time'].isoformat(),
                'days_held': (datetime.now() - pos['entry_time']).days
            })

        return jsonify({
            'success': True,
            'data': {
                'count': positions_summary['count'],
                'total_value': positions_summary['total_value'],
                'total_unrealized_pnl': positions_summary['total_unrealized_pnl'],
                'positions': formatted_positions
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/trades')
def get_trades():
    """Get recent trades."""
    try:
        limit = 20
        trades = storage.get_all_trades(limit=limit)

        formatted_trades = []
        for trade in trades:
            formatted_trades.append({
                'trade_id': trade['trade_id'],
                'type': trade['trade_type'],
                'asset': trade['asset'],
                'timestamp': trade['timestamp'].isoformat(),
                'price': f"{float(trade['price']):.4f}",
                'units': f"{float(trade['units']):.6f}",
                'value': f"{float(trade['value']):.2f}",
                'fee': f"{float(trade['fee']):.2f}",
                'profit_loss': f"{float(trade.get('profit_loss', 0)):.2f}" if trade['trade_type'] == 'EXIT' else '-',
                'profit_loss_pct': f"{float(trade.get('profit_loss_percentage', 0)):.2f}" if trade['trade_type'] == 'EXIT' else '-',
                'exit_reason': trade.get('exit_reason', '-')
            })

        return jsonify({
            'success': True,
            'data': formatted_trades,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/statistics')
def get_statistics():
    """Get trading statistics."""
    try:
        all_trades = storage.get_all_trades()

        if not all_trades:
            return jsonify({
                'success': True,
                'data': {
                    'total_trades': 0,
                    'entries': 0,
                    'exits': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'total_fees': 0,
                    'total_pnl': 0,
                    'avg_pnl': 0
                }
            })

        entries = [t for t in all_trades if t['trade_type'] == 'ENTRY']
        exits = [t for t in all_trades if t['trade_type'] == 'EXIT']

        total_fees = sum(float(t['fee']) for t in all_trades)

        if exits:
            exit_pnls = [float(t.get('profit_loss', 0)) for t in exits if t.get('profit_loss') is not None]
            winning_trades = [pnl for pnl in exit_pnls if pnl > 0]
            losing_trades = [pnl for pnl in exit_pnls if pnl <= 0]
            total_pnl = sum(exit_pnls)
            avg_pnl = total_pnl / len(exits)
            win_rate = len(winning_trades) / len(exits) * 100
        else:
            winning_trades = []
            losing_trades = []
            total_pnl = 0
            avg_pnl = 0
            win_rate = 0

        return jsonify({
            'success': True,
            'data': {
                'total_trades': len(all_trades),
                'entries': len(entries),
                'exits': len(exits),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': f"{win_rate:.1f}",
                'total_fees': f"{total_fees:.2f}",
                'total_pnl': f"{total_pnl:.2f}",
                'avg_pnl': f"{avg_pnl:.2f}"
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio_history')
def get_portfolio_history():
    """Get portfolio history for chart."""
    try:
        days = 30
        history = storage.get_portfolio_history(days=days)

        data = []
        for snapshot in history:
            data.append({
                'timestamp': snapshot['timestamp'].isoformat(),
                'total_value': float(snapshot['total_value']),
                'cash': float(snapshot['cash']),
                'positions_value': float(snapshot['positions_value'])
            })

        return jsonify({
            'success': True,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def run_gui(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask GUI application."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    host = config['gui']['host']
    port = config['gui']['port']
    debug = config['gui']['debug']

    print(f"Starting Trading Bot Dashboard on http://{host}:{port}")
    run_gui(host=host, port=port, debug=debug)
