"""
Enhanced Fundamental Analysis Service - AUTO VALUATION ENGINE V6.0
PRODUCTION READY - INSTITUTION GRADE
- MOS vs Profitability: DEEP VALUE (RISKY) untuk undervalued unprofitable
- Soft cap outlier (penalty, not reject)
- Sub-sector terminal growth adjustment
- Method diversity rule (avoid same-type methods)
- Company-specific adjustments
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime

class FundamentalAnalyzer:
    """Professional fundamental analysis with Auto Valuation Engine"""
    
    def __init__(self):
        self.default_discount_rate = 0.105  # 10.5% (WACC untuk Indonesia)
        self.terminal_growth_rate = 0.025   # 2.5% (default)
        
        # Growth cap per sector
        self.growth_cap_map = {
            'BANK': 0.08,
            'CONSUMER': 0.10,
            'COMMODITY': 0.06,
            'TELCO': 0.07,
            'TECH': 0.15,
            'GENERAL': 0.08
        }
        
        # FIX 3: Sub-sector terminal growth adjustment
        self.sub_sector_terminal_growth = {
            'Tobacco': 0.01,      # Industri rokok = terminal growth rendah
            'Cigarettes': 0.01,
            'Mining': 0.02,
            'Coal': 0.02,
        }
        
        # FIX 5: Company-specific adjustments (next level)
        self.company_specific_adjustment = {
            'GGRM.JK': {'growth_cap': 0.02, 'terminal_growth': 0.01},
            'HMSP.JK': {'growth_cap': 0.03, 'terminal_growth': 0.015},
            'UNVR.JK': {'growth_cap': 0.05, 'terminal_growth': 0.02},
            'ICBP.JK': {'growth_cap': 0.06, 'terminal_growth': 0.02},
        }
        
        # FIX 1: Sector-aware profitability thresholds (lebih longgar)
        self.profitability_thresholds = {
            'BANK': {'min_margin': 15, 'min_roe': 12},
            'CONSUMER': {'min_margin': 2, 'min_roe': 8},
            'COMMODITY': {'min_margin': 5, 'min_roe': 10},
            'TELCO': {'min_margin': 10, 'min_roe': 12},
            'TECH': {'min_margin': -100, 'min_roe': -100},  # Tech bisa rugi
            'GENERAL': {'min_margin': 5, 'min_roe': 10}
        }
        
        # Minimum methods per sector
        self.sector_min_methods = {
            'BANK': 2,
            'TECH': 1,
            'COMMODITY': 2,
            'CONSUMER': 2,
            'TELCO': 2,
            'GENERAL': 2
        }
        
        # Method types classification for diversity rule
        self.method_types = {
            'dcf': 'absolute',
            'ddm': 'absolute',
            'excess': 'absolute',
            'per': 'relative',
            'pbv': 'relative',
            'ps': 'relative'
        }
        
        # Method confidence scoring
        self.method_confidence = {
            'dcf': {'base': 40, 'decay': 0.7},
            'per': {'base': 30, 'decay': 0.8},
            'pbv': {'base': 20, 'decay': 0.6},
            'ddm': {'base': 35, 'decay': 0.75},
            'excess': {'base': 35, 'decay': 0.75},
            'ps': {'base': 25, 'decay': 0.7},
            'graham': {'base': 30, 'decay': 0.8},
            'lynch': {'base': 25, 'decay': 0.7}
        }
        
        # Dynamic Weights per Business Type
        self.company_weights = {
            'BANK': {'pbv': 0.35, 'excess': 0.35, 'graham': 0.2, 'ddm': 0.1},
            'TECH': {'dcf': 0.4, 'ps': 0.4, 'lynch': 0.2},
            'COMMODITY': {'per': 0.4, 'dcf': 0.4, 'graham': 0.2},
            'CONSUMER': {'dcf': 0.4, 'per': 0.3, 'graham': 0.2, 'pbv': 0.1},
            'TELCO': {'dcf': 0.5, 'per': 0.2, 'ddm': 0.2, 'graham': 0.1},
            'GENERAL': {'per': 0.3, 'dcf': 0.3, 'graham': 0.3, 'pbv': 0.1},
        }
        
        # Industry Benchmarking Data
        self.industry_averages = {}
        
        # LQ45-specific outlier limits
        self.outlier_limits = {
            'per_max': 35, 'per_min': 0,
            'pbv_max': 8, 'pbv_min': 0,
            'roe_max': 100, 'roe_min': -50,
            'der_max': 10,
            'growth_max': 100, 'growth_min': -50,
            'margin_max': 100, 'margin_min': -50,
        }
        
        # Market context — read from env so admin can update without code change
        # Update nilai ini di .env: BI_RATE=5.75, INFLATION_RATE=2.5, IHSG_TREND=0.05
        self.market_context = {
            'ihsg_trend': float(os.environ.get('IHSG_TREND', '0.05')),
            'interest_rate': float(os.environ.get('BI_RATE', '5.75')),
            'inflation': float(os.environ.get('INFLATION_RATE', '2.5')),
        }
    
    # ============================================================
    # CLASSIFICATION LAYER
    # ============================================================
    
    def classify_company(self, info: Dict) -> Tuple[str, Optional[str]]:
        """Classify company - returns (sector, sub_sector)"""
        sector = info.get('sector', '')
        industry = info.get('industry', '')
        stock_code = info.get('symbol', '')
        
        # Sub-sector detection
        sub_sector = None
        if 'Tobacco' in industry or 'Cigarettes' in industry:
            sub_sector = 'Tobacco'
        elif 'Mining' in industry or 'Coal' in industry:
            sub_sector = 'Mining'
        
        # Sector classification
        if 'Bank' in industry or 'bank' in industry or sector == 'Financial':
            return 'BANK', sub_sector
        
        if sector == 'Technology' or 'Software' in industry or 'Digital' in industry:
            return 'TECH', sub_sector
        
        if sector in ['Energy', 'Basic Materials']:
            return 'COMMODITY', sub_sector
        
        if sector in ['Consumer Defensive', 'Consumer Cyclical']:
            return 'CONSUMER', sub_sector
        
        if sector == 'Communication Services' or 'Telecom' in industry:
            return 'TELCO', sub_sector
        
        return 'GENERAL', sub_sector
    
    # ============================================================
    # FIX 1: SECTOR-AWARE PROFITABILITY (LEBIH LONGGAR)
    # ============================================================
    
    def is_company_profitable(self, metrics: Dict, company_type: str) -> bool:
        """Sector-aware profitability check - lebih longgar"""
        thresholds = self.profitability_thresholds.get(company_type, self.profitability_thresholds['GENERAL'])
        
        margin = metrics.get('net_profit_margin', 0)
        roe = metrics.get('roe', 0)
        
        # Tech companies are evaluated differently
        if company_type == 'TECH':
            return True  # Tech bisa rugi dan tetap dianggap investable
        
        # Consumer staples bisa margin tipis
        return margin > thresholds['min_margin'] and roe > thresholds['min_roe']
    
    # ============================================================
    # FIX 2: SOFT CAP OUTLIER (PENALTY, NOT REJECT)
    # ============================================================
    
    def apply_outlier_penalty(self, fair_value: float, current_price: float, confidence: float) -> float:
        """Apply penalty for extreme valuations instead of rejecting"""
        if fair_value > current_price * 3:
            # Penalty: reduce confidence by 50%
            return confidence * 0.5
        if fair_value > current_price * 2:
            # Minor penalty for 2-3x
            return confidence * 0.8
        return confidence
    
    # ============================================================
    # FIX 3: TERMINAL GROWTH ADJUSTMENT
    # ============================================================
    
    def get_terminal_growth(self, company_type: str, sub_sector: Optional[str], stock_code: str) -> float:
        """Get terminal growth rate with sub-sector and company adjustment"""
        # Check company-specific adjustment first
        if stock_code in self.company_specific_adjustment:
            return self.company_specific_adjustment[stock_code].get('terminal_growth', 0.02)
        
        # Check sub-sector adjustment
        if sub_sector and sub_sector in self.sub_sector_terminal_growth:
            return self.sub_sector_terminal_growth[sub_sector]
        
        # Default by sector
        sector_terminal = {
            'BANK': 0.025,
            'CONSUMER': 0.02,
            'COMMODITY': 0.02,
            'TELCO': 0.02,
            'TECH': 0.03,
            'GENERAL': 0.025
        }
        return sector_terminal.get(company_type, 0.025)
    
    # ============================================================
    # GET GROWTH CAP
    # ============================================================
    
    def get_growth_cap(self, company_type: str, sub_sector: Optional[str], stock_code: str) -> float:
        """Get growth cap with company-specific adjustment"""
        # Check company-specific adjustment first
        if stock_code in self.company_specific_adjustment:
            return self.company_specific_adjustment[stock_code].get('growth_cap', 0.08)
        
        base_cap = self.growth_cap_map.get(company_type, 0.08)
        
        # Sub-sector adjustment (lebih rendah untuk mature industries)
        if sub_sector == 'Tobacco':
            return min(base_cap, 0.03)
        elif sub_sector == 'Mining':
            return min(base_cap, 0.05)
        
        return base_cap
    
    # ============================================================
    # QUALITY FILTER
    # ============================================================
    
    def quality_check(self, metrics: Dict, company_type: str) -> Dict:
        """Quality filter for LQ45 bluechip companies"""
        result = {'passed': True, 'reasons': []}
        
        if company_type == 'BANK':
            roe = metrics.get('roe', 0)
            npl = metrics.get('npl_ratio', 10)
            
            if roe < 12:
                result['passed'] = False
                result['reasons'].append(f'ROE terlalu rendah: {roe:.1f}% (min 12%)')
            if npl > 5:
                result['passed'] = False
                result['reasons'].append(f'NPL terlalu tinggi: {npl:.1f}% (max 5%)')
                
        elif company_type == 'CONSUMER':
            roe = metrics.get('roe', 0)
            if roe < 8:
                result['passed'] = False
                result['reasons'].append(f'ROE terlalu rendah: {roe:.1f}% (min 8%)')
                
        elif company_type == 'TECH':
            revenue_growth = metrics.get('revenue_growth_1y', 0)
            if revenue_growth < 5:  # Diturunkan dari 10 menjadi 5
                result['passed'] = False
                result['reasons'].append(f'Revenue growth terlalu rendah: {revenue_growth:.1f}% (min 5%)')
        
        return result
    
    # ============================================================
    # MARKET CONTEXT
    # ============================================================
    
    def get_adjusted_discount_rate(self) -> float:
        """Adjust discount rate based on market context"""
        rate = self.default_discount_rate
        
        if self.market_context['interest_rate'] > 6:
            rate += 0.01
        elif self.market_context['interest_rate'] < 5:
            rate -= 0.005
        
        return rate
    
    # ============================================================
    # CORE VALUATION METHODS
    # ============================================================
    
    def _calculate_dcf(self, info: Dict, financials: pd.DataFrame, 
                       cashflow: pd.DataFrame, company_type: str, 
                       sub_sector: Optional[str], stock_code: str,
                       current_price: float) -> Dict:
        """DCF Valuation dengan growth cap dan terminal growth adjustment"""
        
        if company_type == 'BANK':
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        shares_outstanding = info.get('sharesOutstanding', 1)
        discount_rate = self.get_adjusted_discount_rate()
        terminal_growth = self.get_terminal_growth(company_type, sub_sector, stock_code)
        
        # Get FCF
        if not cashflow.empty and 'Free Cash Flow' in cashflow.index:
            fcf_values = cashflow.loc['Free Cash Flow'].dropna().values
            latest_fcf = fcf_values[0] if len(fcf_values) > 0 else 0
            fcf_hist = fcf_values[:5]
        else:
            latest_fcf = info.get('freeCashflow', 0)
            fcf_hist = []
        
        # Commodity cycle adjustment
        if company_type == 'COMMODITY' and len(fcf_hist) >= 3:
            normalized_fcf = np.mean(fcf_hist[:3])
            latest_fcf = normalized_fcf
        
        # Revenue-based DCF untuk tech dengan FCF negatif
        if latest_fcf <= 0 and company_type == 'TECH':
            revenue = 0
            if not financials.empty and 'Total Revenue' in financials.index:
                revenue = financials.loc['Total Revenue'].iloc[0]
            if revenue == 0:
                revenue = info.get('totalRevenue', 0)
            
            if revenue > 0:
                profit_margin = 0.15
                projected_profit = revenue * profit_margin
                max_growth = self.get_growth_cap(company_type, sub_sector, stock_code)
                growth_rate = min(0.15, max_growth)
                
                fair_value = (projected_profit / (discount_rate - growth_rate)) / shares_outstanding
                if fair_value > 0 and fair_value < 100000:
                    confidence = 40
                    confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
                    return {'fair_value': round(fair_value, 2), 'valid': True, 'confidence': confidence}
        
        if latest_fcf <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        # Calculate historical growth
        if len(fcf_hist) >= 2:
            growth_rates = []
            for i in range(len(fcf_hist)-1):
                if fcf_hist[i+1] > 0:
                    gr = (fcf_hist[i] - fcf_hist[i+1]) / fcf_hist[i+1]
                    growth_rates.append(gr)
            historical_growth = np.mean(growth_rates) if growth_rates else 0.03
        else:
            historical_growth = 0.03
        
        # Apply growth cap
        max_growth = self.get_growth_cap(company_type, sub_sector, stock_code)
        base_growth = min(max(historical_growth, 0.02), max_growth)
        
        growth_rates = [base_growth, base_growth*0.9, base_growth*0.8, base_growth*0.7, base_growth*0.6]
        
        # PV Calculation
        pv_fcf = 0
        projected_fcf = latest_fcf
        for i, growth in enumerate(growth_rates):
            projected_fcf *= (1 + growth)
            pv_fcf += projected_fcf / ((1 + discount_rate) ** (i + 1))
        
        terminal_value = projected_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
        pv_terminal = terminal_value / ((1 + discount_rate) ** 5)
        
        enterprise_value = pv_fcf + pv_terminal
        total_debt = info.get('totalDebt', 0)
        cash = info.get('totalCash', 0)
        equity_value = enterprise_value - total_debt + cash
        fair_value = equity_value / shares_outstanding if shares_outstanding else 0
        
        # Sanity check
        if fair_value > 100000:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        confidence = 40
        confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
        
        return {'fair_value': round(max(0, fair_value), 2), 'valid': fair_value > 0, 'confidence': confidence}
    
    def _calculate_per_based(self, info: Dict, company_type: str, current_price: float) -> Dict:
        """PER-based valuation dengan fallback data"""
        eps_forward = info.get('forwardEps') or info.get('trailingEps') or 0
        
        if eps_forward <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        sector_pe_map = {
            'BANK': 12, 'TECH': 20, 'COMMODITY': 10,
            'CONSUMER': 18, 'TELCO': 14, 'GENERAL': 15
        }
        sector_pe = sector_pe_map.get(company_type, 15)
        
        fair_value = eps_forward * sector_pe
        confidence = 30
        confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
        
        return {'fair_value': round(fair_value, 2), 'valid': True, 'confidence': confidence}
    
    def _calculate_pbv_based(self, info: Dict, company_type: str, current_price: float) -> Dict:
        """PBV-based valuation - NOT for TECH companies"""
        if company_type == 'TECH':
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        bvps = info.get('bookValue', 0)
        if bvps <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        sector_pbv_map = {
            'BANK': 2.0, 'COMMODITY': 1.5,
            'CONSUMER': 3.0, 'TELCO': 2.5, 'GENERAL': 2.0
        }
        sector_pbv = sector_pbv_map.get(company_type, 2.0)
        
        fair_value = bvps * sector_pbv
        confidence = 20
        confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
        
        return {'fair_value': round(fair_value, 2), 'valid': True, 'confidence': confidence}
    
    def _calculate_ddm(self, info: Dict, current_price: float) -> Dict:
        """Dividend Discount Model"""
        dividend_per_share = info.get('dividendRate', 0)
        if dividend_per_share == 0:
            dividend_yield = info.get('dividendYield', 0)
            current_price = info.get('currentPrice', 0)
            dividend_per_share = current_price * dividend_yield if current_price else 0
        
        if dividend_per_share <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        roe = info.get('returnOnEquity', 0.11)
        payout_ratio = info.get('payoutRatio', 0.4)
        retention_ratio = 1 - payout_ratio if payout_ratio > 0 else 0.6
        growth_rate = min(roe * retention_ratio, 0.07)
        
        discount_rate = self.get_adjusted_discount_rate()
        if growth_rate >= discount_rate:
            growth_rate = discount_rate - 0.02
        
        fair_value = dividend_per_share / (discount_rate - growth_rate)
        
        # Sanity check
        if fair_value > 100000:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        confidence = 35
        confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
        
        return {'fair_value': round(fair_value, 2), 'valid': fair_value > 0, 'confidence': confidence}
    
    def _calculate_excess_returns(self, info: Dict, company_type: str, current_price: float) -> Dict:
        """Excess Returns Model - KHUSUS untuk BANK saja"""
        if company_type != 'BANK':
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        bvps = info.get('bookValue', 0)
        if bvps <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        roe = info.get('returnOnEquity', 0.11)
        cost_of_equity = self.get_adjusted_discount_rate()
        
        excess_return = roe - cost_of_equity
        
        if excess_return <= 0:
            fair_value = bvps
        else:
            terminal_growth = 0.025
            pv_excess = bvps * excess_return / (cost_of_equity - terminal_growth)
            fair_value = bvps + pv_excess
        
        confidence = 35
        confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
        
        return {'fair_value': round(fair_value, 2), 'valid': True, 'confidence': confidence}
    
    def _calculate_ps_based(self, info: Dict, financials: pd.DataFrame, 
                            company_type: str, current_price: float) -> Dict:
        """Price/Sales ratio - WAJIB untuk TECH companies"""
        if company_type != 'TECH':
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        revenue = 0
        if not financials.empty and 'Total Revenue' in financials.index:
            revenue = financials.loc['Total Revenue'].iloc[0]
        if revenue == 0:
            revenue = info.get('totalRevenue', 0)
        if revenue == 0:
            revenue = info.get('revenue', 0)
        
        shares_outstanding = info.get('sharesOutstanding', 1)
        revenue_per_share = revenue / shares_outstanding if shares_outstanding else 0
        
        if revenue_per_share <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
        
        ps_ratio = 3.0
        fair_value = revenue_per_share * ps_ratio
        
        confidence = 25
        confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
        
        return {'fair_value': round(fair_value, 2), 'valid': True, 'confidence': confidence}
    
    # ============================================================
    # FIX 4: METHOD DIVERSITY RULE
    # ============================================================
    
    def select_best_methods_with_diversity(self, valuation_results: Dict) -> List[Tuple[str, Dict]]:
        """Select top methods with diversity (avoid same-type methods)"""
        valid_methods = [(m, r) for m, r in valuation_results.items() if r.get('valid', False) and r.get('fair_value', 0) > 0]
        
        if not valid_methods:
            return []
        
        # Sort by confidence
        valid_methods.sort(key=lambda x: x[1].get('confidence', 0), reverse=True)
        
        if len(valid_methods) == 1:
            return valid_methods[:1]
        
        # Check if top 2 methods are same type
        top1_type = self.method_types.get(valid_methods[0][0], 'unknown')
        top2_type = self.method_types.get(valid_methods[1][0], 'unknown')
        
        if top1_type == top2_type and len(valid_methods) > 2:
            # Skip the second and take third
            return [valid_methods[0], valid_methods[2]]
        
        return valid_methods[:2]
    
    # ============================================================
    # DYNAMIC WEIGHTING
    # ============================================================
    
    def calculate_dynamic_weights_top2(self, top_methods: List[Tuple[str, Dict]], company_type: str) -> Dict:
        """Calculate weights for top methods based on their confidence"""
        if len(top_methods) == 0:
            return {}
        
        if len(top_methods) == 1:
            return {top_methods[0][0]: 1.0}
        
        # Weight based on confidence ratio
        conf1 = top_methods[0][1].get('confidence', 50)
        conf2 = top_methods[1][1].get('confidence', 50)
        total_conf = conf1 + conf2
        
        return {
            top_methods[0][0]: conf1 / total_conf,
            top_methods[1][0]: conf2 / total_conf
        }
    
    # ============================================================
    # CONFIDENCE LEVEL PER SEKTOR
    # ============================================================
    
    def calculate_sector_confidence(self, company_type: str, metrics: Dict) -> int:
        """Calculate confidence score based on sector"""
        confidence = 0
        
        if company_type == 'BANK':
            if metrics.get('excess_valid', False):
                confidence += 20
            if metrics.get('ddm_valid', False):
                confidence += 15
            if metrics.get('pbv_valid', False):
                confidence += 15
            
        elif company_type == 'TECH':
            if metrics.get('dcf_valid', False):
                confidence += 25
            if metrics.get('ps_valid', False):
                confidence += 25
            if metrics.get('revenue_growth_1y', 0) > 20:
                confidence += 15
                
        elif company_type == 'COMMODITY':
            if metrics.get('per_valid', False):
                confidence += 20
            if metrics.get('dcf_valid', False):
                confidence += 20
        
        return min(100, max(0, confidence))
    
    # ============================================================
    # RANKING SYSTEM
    # ============================================================
    
    def calculate_ranking_score(self, metrics: Dict) -> float:
        """Calculate ranking score for LQ45 screening"""
        mos = metrics.get('margin_of_safety', {}).get('percentage', 0)
        fundamental_score = metrics.get('fundamental_recommendation', {}).get('score', 50)
        confidence = metrics.get('valuation_confidence', {}).get('score', 50)
        
        # MOS bisa negatif, biarkan apa adanya
        score = (mos * 0.4 + fundamental_score * 0.4 + confidence * 0.2)
        return round(score, 2)
    
    def _calculate_graham_value(self, info: Dict, current_price: float) -> Dict:
        """Graham Intrinsic Value: sqrt(22.5 * EPS * BVPS)"""
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        
        if eps <= 0 or bvps <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
            
        try:
            # Graham's Number formula
            fair_value = np.sqrt(22.5 * eps * bvps)
            confidence = 30
            confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
            return {'fair_value': round(float(fair_value), 2), 'valid': True, 'confidence': confidence}
        except:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}

    def _calculate_peter_lynch_value(self, info: Dict, metrics: Dict, current_price: float) -> Dict:
        """Peter Lynch Fair Value: PEG Ratio * Earnings Growth * EPS"""
        eps = info.get('trailingEps', 0)
        growth = metrics.get('revenue_growth_1y', 5) # Default 5%
        
        if eps <= 0:
            return {'fair_value': 0, 'valid': False, 'confidence': 0}
            
        # Peter Lynch logic: Fair value is when PE = Growth Rate
        # PEG = 1 is fair value
        fair_value = eps * growth
        
        confidence = 25
        confidence = self.apply_outlier_penalty(fair_value, current_price, confidence)
        return {'fair_value': round(float(fair_value), 2), 'valid': fair_value > 0, 'confidence': confidence}

    # ============================================================
    # MAIN PUBLIC METHOD
    # ============================================================
    
    def get_complete_fundamental_data(self, stock_code: str) -> Dict:
        """Main entry point - complete fundamental analysis"""
        ticker = yf.Ticker(stock_code)
        info = ticker.info
        financials = ticker.financials
        cashflow = ticker.cashflow
        
        if not info or info.get('currentPrice', 0) == 0:
            return {'error': f'No data available for {stock_code}'}
        
        # Classification dengan company-specific
        company_type, sub_sector = self.classify_company(info)
        
        metrics = self._get_basic_metrics(info, financials)
        metrics['company_type'] = company_type
        metrics['sub_sector'] = sub_sector
        
        current_price = info.get('currentPrice', 0)
        
        # Calculate all valuation methods
        valuation_results = {}
        
        # DCF
        dcf_result = self._calculate_dcf(info, financials, cashflow, company_type, sub_sector, stock_code, current_price)
        valuation_results['dcf'] = dcf_result
        metrics['fair_value_dcf'] = dcf_result['fair_value']
        metrics['dcf_valid'] = dcf_result['valid']
        
        # PER
        per_result = self._calculate_per_based(info, company_type, current_price)
        valuation_results['per'] = per_result
        metrics['fair_value_per'] = per_result['fair_value']
        metrics['per_valid'] = per_result['valid']
        
        # PBV
        pbv_result = self._calculate_pbv_based(info, company_type, current_price)
        valuation_results['pbv'] = pbv_result
        metrics['fair_value_pbv'] = pbv_result['fair_value']
        metrics['pbv_valid'] = pbv_result['valid']
        
        # DDM
        ddm_result = self._calculate_ddm(info, current_price)
        valuation_results['ddm'] = ddm_result
        metrics['fair_value_ddm'] = ddm_result['fair_value']
        metrics['ddm_valid'] = ddm_result['valid']
        
        # Excess Returns (khusus BANK)
        excess_result = self._calculate_excess_returns(info, company_type, current_price)
        valuation_results['excess'] = excess_result
        metrics['fair_value_excess'] = excess_result['fair_value']
        metrics['excess_valid'] = excess_result['valid']
        
        # Graham Intrinsic Value
        graham_result = self._calculate_graham_value(info, current_price)
        valuation_results['graham'] = graham_result
        metrics['fair_value_graham'] = graham_result['fair_value']
        metrics['graham_valid'] = graham_result['valid']
        
        # Peter Lynch Fair Value
        lynch_result = self._calculate_peter_lynch_value(info, metrics, current_price)
        valuation_results['lynch'] = lynch_result
        metrics['fair_value_lynch'] = lynch_result['fair_value']
        metrics['lynch_valid'] = lynch_result['valid']
        
        # P/S untuk TECH
        ps_result = self._calculate_ps_based(info, financials, company_type, current_price)
        valuation_results['ps'] = ps_result
        metrics['fair_value_ps'] = ps_result['fair_value']
        metrics['ps_valid'] = ps_result['valid']
        
        # Hard rule per sector untuk TECH
        if company_type == 'TECH' and not (metrics['dcf_valid'] or metrics['ps_valid']):
            metrics['valuation_status'] = 'INVALID_TECH_VALUATION'
            metrics['fair_value'] = None
            metrics['valuation_methods_used'] = []
            metrics['valuation_method_weights'] = {}
        else:
            # FIX 4: Select methods with diversity
            top_methods = self.select_best_methods_with_diversity(valuation_results)
            min_methods = self.sector_min_methods.get(company_type, 2)
            
            if len(top_methods) == 0:
                metrics['valuation_status'] = 'INVALID'
                metrics['fair_value'] = None
            elif len(top_methods) < min_methods and company_type != 'TECH':
                metrics['valuation_status'] = 'LIMITED'
                metrics['fair_value'] = None
            else:
                metrics['valuation_status'] = 'VALID'
                weights = self.calculate_dynamic_weights_top2(top_methods, company_type)
                
                fair_value_weighted = 0
                for method, weight in weights.items():
                    fair_value_weighted += valuation_results[method]['fair_value'] * weight
                
                metrics['fair_value'] = round(fair_value_weighted, 2)
                metrics['valuation_methods_used'] = [m for m, _ in top_methods]
                metrics['valuation_method_weights'] = {m: round(w*100) for m, w in weights.items()}
        
        # Upside potential (no cap)
        if metrics.get('fair_value') is not None and metrics['fair_value'] > 0:
            upside = ((metrics['fair_value'] - current_price) / current_price * 100) if current_price > 0 else 0
            metrics['upside_potential'] = round(upside, 2)
            metrics['upside_capped'] = False
        else:
            metrics['upside_potential'] = None
            metrics['upside_capped'] = False
        
        # FIX 1: Sector-aware profitability
        is_profitable = self.is_company_profitable(metrics, company_type)
        metrics['is_profitable'] = is_profitable
        
        quality_result = self.quality_check(metrics, company_type)
        metrics['quality_check'] = quality_result
        
        # FIX 1: Margin of Safety dengan gradasi untuk unprofitable companies
        if metrics.get('fair_value') is not None and metrics['fair_value'] > 0:
            metrics['margin_of_safety'] = self._calculate_margin_of_safety(
                metrics['fair_value'], current_price, is_profitable, company_type
            )
        else:
            metrics['margin_of_safety'] = {
                'percentage': None,
                'level': 'N/A',
                'action': 'CANNOT VALUE',
                'description': 'Valuation not available due to insufficient data'
            }
        
        # Valuation Confidence
        confidence_score = self.calculate_sector_confidence(company_type, metrics)
        metrics['valuation_confidence'] = self._calculate_valuation_confidence(metrics, confidence_score)
        
        # Fundamental Recommendation
        metrics['fundamental_recommendation'] = self._get_fundamental_recommendation(metrics, company_type)
        
        # Ranking Score
        metrics['ranking_score'] = self.calculate_ranking_score(metrics)
        
        # Industry Benchmarking (Institutional Feature)
        metrics['industry_benchmarking'] = self._get_industry_benchmarking(metrics, company_type)
        
        # Additional metrics
        metrics['stock_code'] = stock_code
        metrics['current_price'] = current_price
        metrics['sector'] = info.get('sector', 'Unknown')
        metrics['company_type'] = company_type
        metrics['last_updated'] = datetime.now().isoformat()
        
        return metrics

    def update_industry_averages(self, all_stocks_data: List[Dict]):
        """Update industry averages based on a list of analyzed stocks"""
        df = pd.DataFrame(all_stocks_data)
        if df.empty: return
        
        # Group by company_type
        avg_metrics = ['per', 'pbv', 'roe', 'der', 'net_profit_margin']
        for sector, group in df.groupby('company_type'):
            self.industry_averages[sector] = {
                metric: group[metric].mean() for metric in avg_metrics if metric in group.columns
            }
            self.industry_averages[sector]['count'] = len(group)

    def _get_industry_benchmarking(self, metrics: Dict, sector: str) -> Dict:
        """Compare current stock against industry averages"""
        avg = self.industry_averages.get(sector, {})
        if not avg:
            return {'status': 'N/A', 'details': 'No industry data available'}
            
        comparisons = []
        
        # Compare PER
        if metrics.get('per') and avg.get('per'):
            diff = (metrics['per'] - avg['per']) / avg['per'] * 100
            label = "Cheaper" if diff < 0 else "More Expensive"
            comparisons.append(f"PER is {abs(diff):.1f}% {label} than {sector} average")
            
        # Compare ROE
        if metrics.get('roe') and avg.get('roe'):
            diff = metrics['roe'] - avg['roe']
            label = "Higher" if diff > 0 else "Lower"
            comparisons.append(f"ROE is {abs(diff):.1f}% {label} than {sector} average")
            
        # Overall Status
        status = "BETTER" if metrics.get('roe', 0) > avg.get('roe', 0) and metrics.get('per', 100) < avg.get('per', 100) else "MIXED"
        
        return {
            'sector_averages': avg,
            'status': status,
            'comparison_summary': comparisons
        }
    
    def _get_basic_metrics(self, info: Dict, financials: pd.DataFrame) -> Dict:
        """Extract basic financial metrics dengan fallback dan perbaikan DER"""
        # Current Price Fallback
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose', 0)
        
        eps_ttm = info.get('trailingEps', 0)
        eps_forward = info.get('forwardEps') or eps_ttm or 0
        
        bvps = info.get('bookValue', 0)
        
        per_ttm = self._cap_value(info.get('trailingPE', 0), 'per') if info.get('trailingPE') else 0
        pbv = self._cap_value(info.get('priceToBook', 0), 'pbv') if info.get('priceToBook') else 0
        
        # PERBAIKAN DER (Debt to Equity Ratio)
        total_debt = info.get('totalDebt')
        total_equity = info.get('totalShareholderEquity')
        
        # Debug Log (Internal)
        # print(f"DEBUG DER: debt={total_debt}, equity={total_equity}")
        
        der = None
        if total_debt is not None and total_equity is not None and total_equity > 0:
            # Pastikan skala sama
            raw_der = total_debt / total_equity
            der = round(raw_der, 2)
            
            # Sanity check: Jika DER > 100 untuk non-bank, mungkin ada kesalahan skala
            sector = info.get('sector', '')
            if sector != 'Financial Services' and der > 50:
                der = der / 1000  # Fallback jika salah satu dalam jutaan, lainnya dalam ribuan
        
        # Fallback DER dari info jika manual gagal
        if der is None or der == 0:
            der = info.get('debtToEquity')
            if der and der > 10: # Yahoo sering kasih d/e dalam persen (misal 80.5 untuk 0.805)
                der = der / 100
        
        der = self._cap_value(der if der is not None else 0, 'der')
        
        # ROE
        roe = info.get('returnOnEquity', 0)
        if roe and abs(roe) < 1:
            roe = roe * 100
        roe = self._cap_value(roe, 'roe')
        
        # ROA (Return on Assets)
        roa = info.get('returnOnAssets', 0)
        if roa and abs(roa) < 1:
            roa = roa * 100
            
        # Operating Margin
        op_margin = info.get('operatingMargins', 0)
        if op_margin and abs(op_margin) < 1:
            op_margin = op_margin * 100
            
        # Net Profit Margin
        net_profit_margin = info.get('profitMargins', 0)
        if net_profit_margin and abs(net_profit_margin) < 1:
            net_profit_margin = net_profit_margin * 100
        
        # Revenue growth
        revenue_growth = 0
        if not financials.empty and 'Total Revenue' in financials.index:
            revenues = financials.loc['Total Revenue'].dropna().values
            if len(revenues) >= 2:
                revenue_growth = (revenues[0] - revenues[1]) / abs(revenues[1]) * 100 if revenues[1] != 0 else 0
        
        # Bank-specific metrics
        npl_ratio = info.get('nonPerformingLoans', 0)
        if npl_ratio and npl_ratio < 1:
            npl_ratio = npl_ratio * 100
            
        nim = info.get('netInterestMargin', 0)
        if nim and nim < 1:
            nim = nim * 100
        
        return {
            'eps_ttm': round(float(eps_ttm), 2),
            'eps_forward': round(float(eps_forward), 2),
            'bvps': round(float(bvps), 2),
            'per_ttm': round(float(per_ttm), 2),
            'pbv': round(float(pbv), 2),
            'der': round(float(der), 2) if der is not None else None,
            'roe': round(float(roe), 2),
            'roa': round(float(roa), 2),
            'operating_margin': round(float(op_margin), 2),
            'net_profit_margin': round(float(net_profit_margin), 2),
            'revenue_growth_1y': round(float(revenue_growth), 2),
            'npl_ratio': round(float(npl_ratio), 2),
            'nim': round(float(nim), 2),
        }
    
    def _cap_value(self, value: float, key: str) -> float:
        """Cap outlier values"""
        limits = self.outlier_limits
        if key in limits:
            return max(limits[f'{key}_min'], min(limits[f'{key}_max'], value))
        return value
    
    def _calculate_margin_of_safety(self, fair_value: float, current_price: float, 
                                     is_profitable: bool, company_type: str) -> Dict:
        """Calculate margin of safety - NO LONGER OVERRIDES HIGH MOS"""
        if fair_value is None or fair_value == 0 or current_price == 0:
            return {'percentage': None, 'level': 'N/A', 'action': 'CANNOT VALUE'}
        
        mos = ((fair_value - current_price) / fair_value) * 100
        mos = max(-100, min(500, mos))  # Allow up to 500% upside
        
        # FIX 1: MOS determines action, profitability adds risk label
        if mos >= 50:
            level = 'Very High'
            if is_profitable:
                action = 'STRONG BUY'
            else:
                action = 'DEEP VALUE (RISKY)'
        elif mos >= 30:
            level = 'High'
            if is_profitable:
                action = 'BUY'
            else:
                action = 'SPECULATIVE BUY'
        elif mos >= 15:
            level = 'Moderate'
            if is_profitable:
                action = 'ACCUMULATE'
            else:
                action = 'SPECULATIVE HOLD'
        elif mos >= 0:
            level = 'Low'
            action = 'HOLD'
        elif mos >= -20:
            level = 'Negative'
            action = 'WAIT'
        else:
            level = 'Very Negative'
            action = 'AVOID'
        
        return {
            'percentage': round(mos, 2),
            'level': level,
            'action': action,
            'description': f"Diskon {abs(round(mos, 2))}% dari fair value" if mos > 0 else f"Premium {abs(round(mos, 2))}% dari fair value"
        }
    
    def _calculate_valuation_confidence(self, metrics: Dict, sector_confidence: int) -> Dict:
        """Calculate overall valuation confidence"""
        confidence_score = sector_confidence
        
        if metrics.get('is_profitable', False):
            confidence_score += 20
        else:
            confidence_score -= 10  # Kurangi penalty (dari -30 jadi -10)
        
        if len(metrics.get('valuation_methods_used', [])) >= 2:
            confidence_score += 10
        
        confidence_score = min(100, max(0, confidence_score))
        
        if confidence_score >= 70:
            level = 'HIGH'
            interpretation = 'Valuation is reliable'
        elif confidence_score >= 40:
            level = 'MEDIUM'
            interpretation = 'Valuation has limitations'
        else:
            level = 'LOW'
            interpretation = 'Valuation may be unreliable'
        
        return {
            'score': confidence_score,
            'level': level,
            'interpretation': interpretation
        }
    
    def _get_fundamental_recommendation(self, metrics: Dict, company_type: str) -> Dict:
        """Generate fundamental recommendation based on all metrics"""
        mos = metrics.get('margin_of_safety', {}).get('percentage')
        
        if mos is None:
            return {
                'score': 0,
                'recommendation': 'CANNOT VALUE',
                'summary': 'Insufficient data for valuation'
            }
        
        # Recommendation based primarily on MOS
        if mos >= 50:
            final_score, recommendation = 85, 'STRONG BUY'
        elif mos >= 30:
            final_score, recommendation = 75, 'BUY'
        elif mos >= 15:
            final_score, recommendation = 65, 'ACCUMULATE'
        elif mos >= 0:
            final_score, recommendation = 50, 'HOLD'
        elif mos >= -20:
            final_score, recommendation = 35, 'WAIT'
        else:
            final_score, recommendation = 20, 'AVOID'
        
        return {
            'score': round(final_score, 2),
            'recommendation': recommendation,
            'summary': f"Fundamental score {round(final_score, 2)}% - {recommendation}"
        }


# Global instance
fundamental_analyzer = FundamentalAnalyzer()


# ============================================================
# LQ45 RANKING UTILITY
# ============================================================

def rank_lq45_stocks(stock_codes: List[str]) -> List[Dict]:
    """Rank LQ45 stocks by valuation score"""
    results = []
    
    for code in stock_codes:
        try:
            data = fundamental_analyzer.get_complete_fundamental_data(code)
            if 'error' not in data:
                results.append({
                    'stock_code': code,
                    'company_type': data.get('company_type', 'UNKNOWN'),
                    'valuation_status': data.get('valuation_status', 'UNKNOWN'),
                    'ranking_score': data.get('ranking_score', 0),
                    'fair_value': data.get('fair_value'),
                    'current_price': data.get('current_price', 0),
                    'upside_potential': data.get('upside_potential'),
                    'mos': data.get('margin_of_safety', {}).get('percentage'),
                    'recommendation': data.get('fundamental_recommendation', {}).get('recommendation', 'N/A'),
                    'is_profitable': data.get('is_profitable', False),
                })
        except Exception as e:
            print(f"Error ranking {code}: {e}")
    
    # Filter hanya yang VALID
    valid_results = [r for r in results if r.get('valuation_status') == 'VALID']
    valid_results.sort(key=lambda x: x.get('ranking_score', 0), reverse=True)
    return valid_results