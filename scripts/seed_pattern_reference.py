"""
Seed script for pattern_reference table.

Populates ground-truth taught-behavior for every pattern/indicator the system
detects. TEXTBOOK EXPECTATION only — not validated behavior.

Run after migration 0050_pattern_reference.sql.
Re-runnable: uses INSERT...ON CONFLICT DO UPDATE.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from sqlalchemy import create_engine, text
from config import settings

ROWS = [
    # ─────────────────────────────────────────────────────────────────────────
    # CANDLESTICK PATTERNS — detected in ta/candlesticks.py
    # direction field in pattern_memory captures long/short for each instance
    # ─────────────────────────────────────────────────────────────────────────
    dict(
        pattern_type="doji",
        category="bilateral",
        expected_direction="bidirectional",
        description=(
            "Single bar with nearly equal open and close; real body < 10% of the "
            "high-low range. Represents a session-long battle that ends in equilibrium."
        ),
        taught_expectation=(
            "Signals pause or potential change in direction. By itself it is NOT "
            "actionable; the next bar's direction and close determine the resolution. "
            "In an uptrend, a doji warns of exhaustion; in a downtrend, of seller fatigue."
        ),
        confirmation_condition=(
            "Next bar closes decisively in one direction (gap or strong candle). "
            "A bullish close above the doji high confirms a bull reversal; a bearish "
            "close below the doji low confirms a bear reversal."
        ),
        invalidation_condition=(
            "No meaningful follow-through — next bar is also small and indecisive. "
            "Or the prior trend simply resumes without a pause."
        ),
        invalidation_becomes=None,
        source_note=(
            "Nison 'Japanese Candlestick Charting Techniques'; widely cited as one of "
            "the oldest single-bar signals."
        ),
    ),
    dict(
        pattern_type="spinning_top",
        category="bilateral",
        expected_direction="bidirectional",
        description=(
            "Small real body with upper AND lower wicks each longer than the body. "
            "Similar to doji but with a more visible body; also signals indecision."
        ),
        taught_expectation=(
            "Neither bulls nor bears in control during the session. Direction depends "
            "entirely on context (prior trend) and the following bar's behavior. "
            "Slightly weaker signal than doji — smaller body means less commitment."
        ),
        confirmation_condition=(
            "Next bar's direction and close. Requires confirmation in the intended "
            "direction before acting."
        ),
        invalidation_condition=(
            "No follow-through; prior trend continues without hesitation."
        ),
        invalidation_becomes=None,
        source_note="Nison; Bulkowski 'Encyclopedia of Candlestick Charts'.",
    ),
    dict(
        pattern_type="marubozu",
        category="bilateral",
        expected_direction="bidirectional",
        description=(
            "Long real body (>90% of range) with minimal or no wicks. Bullish "
            "marubozu = buyers controlled the entire session; bearish = sellers. "
            "Direction is encoded in the pattern_memory direction field (long/short)."
        ),
        taught_expectation=(
            "Strong one-sided momentum. Bullish marubozu signals high probability of "
            "continuation higher; bearish signals continuation lower. Often considered "
            "self-confirming due to the absence of rejection wicks."
        ),
        confirmation_condition=(
            "For bullish: next bar holds above marubozu close (does not reverse back "
            "into the body). For bearish: next bar holds below close. Volume surge "
            "on the marubozu bar strengthens the signal."
        ),
        invalidation_condition=(
            "Immediate next-bar reversal that closes back through the marubozu body "
            "(engulfing reversal)."
        ),
        invalidation_becomes=(
            "A marubozu immediately engulfed by the opposite-direction next bar is a "
            "strong trap signal in the opposing direction (e.g. bull marubozu followed "
            "by bearish engulfing → bearish)."
        ),
        source_note="Nison; Bulkowski; ubiquitous in Japanese candlestick literature.",
    ),
    dict(
        pattern_type="hammer",
        category="reversal",
        expected_direction="up",
        description=(
            "Small body at the top of the range with a long lower shadow (≥2× body) "
            "appearing after a downtrend. Intraday sellers drove price low, but buyers "
            "reclaimed most of the ground by close."
        ),
        taught_expectation=(
            "Bullish reversal signal at the end of a downtrend; at minimum a temporary "
            "low. The longer the lower shadow, the more significant the buyer response."
        ),
        confirmation_condition=(
            "Next bar closes above the hammer's body (conservative: close above the "
            "hammer's close). Stricter: close above the hammer's high. Volume should "
            "be above average on the confirmation bar."
        ),
        invalidation_condition=(
            "Next bar closes below the hammer's low — sellers remain in control."
        ),
        invalidation_becomes=None,
        source_note="Nison; Bulkowski; requires prior downtrend context (coded in detection).",
    ),
    dict(
        pattern_type="hanging_man",
        category="reversal",
        expected_direction="down",
        description=(
            "Same shape as a hammer (small body at top, long lower shadow ≥2× body) "
            "but appearing after an uptrend. The lower shadow shows intraday selling "
            "pressure that buyers just barely overcame."
        ),
        taught_expectation=(
            "Potential bearish reversal at the end of an uptrend. Weaker signal than "
            "most reversal candles — requires mandatory confirmation because buyers "
            "technically won the session."
        ),
        confirmation_condition=(
            "Next bar closes BELOW the hanging man's body (below its open for a "
            "bearish day or below its close)."
        ),
        invalidation_condition=(
            "Next bar closes above the hanging man's high — uptrend continues."
        ),
        invalidation_becomes=None,
        source_note="Nison; candlestick_concepts table has analogous rules.",
    ),
    dict(
        pattern_type="inverted_hammer",
        category="reversal",
        expected_direction="up",
        description=(
            "Small body at the bottom of the range with a long upper shadow (≥2× body) "
            "after a downtrend. Buyers tried to push price up intraday; sellers reclaimed "
            "some but not all the ground."
        ),
        taught_expectation=(
            "Potential bullish reversal; weaker than hammer because the close is near "
            "the low of the session. Requires confirmation."
        ),
        confirmation_condition=(
            "Next bar closes above the inverted hammer's high — buyers follow through "
            "and overcome the intraday resistance."
        ),
        invalidation_condition=(
            "Next bar closes below the inverted hammer's low — further downside."
        ),
        invalidation_becomes=None,
        source_note="Nison; common in Japanese candlestick curricula.",
    ),
    dict(
        pattern_type="shooting_star",
        category="reversal",
        expected_direction="down",
        description=(
            "Small body at the bottom of the range with a long upper shadow (≥2× body) "
            "after an uptrend. Buyers pushed price sharply up intraday, then sellers "
            "reclaimed most of that ground."
        ),
        taught_expectation=(
            "Bearish reversal at end of uptrend; analogous to hanging man but with the "
            "long shadow on top. The rejection from highs shows supply pressure."
        ),
        confirmation_condition=(
            "Next bar closes below the shooting star's body (below its low on a "
            "strong follow-through)."
        ),
        invalidation_condition=(
            "Next bar closes above the shooting star's high — uptrend continues."
        ),
        invalidation_becomes=None,
        source_note="Nison; Bulkowski.",
    ),
    dict(
        pattern_type="bullish_engulfing",
        category="reversal",
        expected_direction="up",
        description=(
            "Two-bar pattern after a downtrend: a bearish bar followed by a larger "
            "bullish bar whose real body completely engulfs the prior bar's body. "
            "Day-2 buyers overwhelm all of day-1's sellers."
        ),
        taught_expectation=(
            "Strong bullish reversal signal. One of the most reliable two-bar reversal "
            "patterns. Volume on the engulfing bar should exceed day-1's volume."
        ),
        confirmation_condition=(
            "Subsequent close above the engulfing bar's close; or third bar is also "
            "bullish. Volume surge on the engulfing bar is confirmatory."
        ),
        invalidation_condition=(
            "Close below the engulfing bar's low — sellers regain control."
        ),
        invalidation_becomes=(
            "Failed engulfing (next bar closes below engulfing low) → continuation of "
            "downtrend; the trapped longs intensify the move lower."
        ),
        source_note="Nison; Bulkowski rates this as a high-reliability reversal.",
    ),
    dict(
        pattern_type="bearish_engulfing",
        category="reversal",
        expected_direction="down",
        description=(
            "Two-bar after an uptrend: bullish bar followed by a larger bearish bar "
            "engulfing the prior body. Sellers completely overwhelm buyers."
        ),
        taught_expectation=(
            "Strong bearish reversal. Sellers not only erase day-1 gains but close "
            "below day-1's open, showing decisive shift in sentiment."
        ),
        confirmation_condition=(
            "Subsequent close below the engulfing bar's close; volume surge."
        ),
        invalidation_condition=(
            "Close above the engulfing bar's high — buyers absorb the sellers."
        ),
        invalidation_becomes=(
            "Failed bearish engulfing → trapped shorts cover → bullish continuation."
        ),
        source_note="Nison; Bulkowski.",
    ),
    dict(
        pattern_type="bullish_harami",
        category="reversal",
        expected_direction="up",
        description=(
            "Two-bar after a downtrend: large bearish bar (the 'mother') followed by a "
            "small bullish bar whose body is entirely inside the mother bar's body. "
            "The small bar shows diminishing selling momentum."
        ),
        taught_expectation=(
            "Weak bullish reversal signal. Suggests sellers are losing force but does "
            "NOT yet show buyers dominating. Requires stronger confirmation than engulfing."
        ),
        confirmation_condition=(
            "Third bar closes above the mother bar's body (the bearish bar's open). "
            "A close above the small bullish bar's high alone is insufficient."
        ),
        invalidation_condition=(
            "Close below the small bar's low; sellers extend the downtrend."
        ),
        invalidation_becomes=None,
        source_note=(
            "Nison; Bulkowski notes harami as lower reliability than engulfing; "
            "often treated as a pause, not a reversal."
        ),
    ),
    dict(
        pattern_type="bearish_harami",
        category="reversal",
        expected_direction="down",
        description=(
            "Two-bar after an uptrend: large bullish bar followed by a small bearish "
            "bar contained inside the mother's body. Diminishing buying momentum."
        ),
        taught_expectation=(
            "Weak bearish reversal. Requires confirmation — the small inside bar alone "
            "is insufficient to call a top."
        ),
        confirmation_condition=(
            "Third bar closes below the mother bar's body (below the bullish bar's "
            "open)."
        ),
        invalidation_condition=(
            "Close above mother bar's high — uptrend continues."
        ),
        invalidation_becomes=None,
        source_note="Nison; Bulkowski.",
    ),
    dict(
        pattern_type="piercing",
        category="reversal",
        expected_direction="up",
        description=(
            "Two-bar after a downtrend: large bearish bar followed by a bullish bar "
            "that opens BELOW the prior day's low then closes ABOVE the midpoint of the "
            "prior bar's real body. Buyers reclaim more than half of the prior loss."
        ),
        taught_expectation=(
            "Moderate bullish reversal; stronger than harami (closes past midpoint) "
            "but weaker than engulfing (doesn't exceed prior open). "
            "The deeper the penetration, the stronger the signal."
        ),
        confirmation_condition=(
            "Subsequent close above the piercing bar's close; or above the prior bar's "
            "open (which completes to a 'bullish engulfing')."
        ),
        invalidation_condition=(
            "Close below the piercing bar's low — sellers absorb the buying."
        ),
        invalidation_becomes=None,
        source_note="Nison; Bulkowski.",
    ),
    dict(
        pattern_type="dark_cloud_cover",
        category="reversal",
        expected_direction="down",
        description=(
            "Two-bar after an uptrend: large bullish bar followed by a bearish bar "
            "opening ABOVE the prior high then closing BELOW the midpoint of the prior "
            "bar's body. Sellers overwhelm buyers past the 50% retracement."
        ),
        taught_expectation=(
            "Moderate bearish reversal; the mirror of piercing. More significant when "
            "the close penetrates deeper than 50% of the prior bar."
        ),
        confirmation_condition=(
            "Next close below the dark-cloud bar's close; or below the prior bar's "
            "open."
        ),
        invalidation_condition=(
            "Close above the dark-cloud bar's high — buyers absorb selling."
        ),
        invalidation_becomes=None,
        source_note="Nison; Bulkowski.",
    ),
    dict(
        pattern_type="tweezer_top",
        category="reversal",
        expected_direction="down",
        description=(
            "Two consecutive bars with matching or near-matching highs (within ~0.3%) "
            "after an uptrend. Price was rejected at the same level twice, confirming "
            "overhead supply at that price."
        ),
        taught_expectation=(
            "Bearish reversal; double rejection at a price level establishes resistance. "
            "Reliability improves significantly when the pattern forms at a prior "
            "swing high, S/R level, or round number."
        ),
        confirmation_condition=(
            "Close below the low of the two-bar pattern."
        ),
        invalidation_condition=(
            "Close above the matched highs — buyers break through the resistance."
        ),
        invalidation_becomes=(
            "A close above the matched highs THAT HOLDS on a subsequent pullback retest "
            "(prior resistance holds as support) → the double-tested level has flipped "
            "to support → LONG continuation signal."
        ),
        source_note="Nison; common usage in support/resistance analysis.",
    ),
    dict(
        pattern_type="tweezer_bottom",
        category="reversal",
        expected_direction="up",
        description=(
            "Two consecutive bars with matching or near-matching lows after a downtrend. "
            "Price was supported at the same level twice, confirming demand at that price."
        ),
        taught_expectation=(
            "Bullish reversal; double-tested support. Reliability improves at prior "
            "swing lows, S/R zones, or Fibonacci levels."
        ),
        confirmation_condition=(
            "Close above the high of the two-bar pattern."
        ),
        invalidation_condition=(
            "Close below the matched lows — support breaks."
        ),
        invalidation_becomes=(
            "A close below the matched lows that holds on retest from below (prior "
            "support now acts as resistance) → double-tested support has flipped to "
            "resistance → SHORT continuation signal."
        ),
        source_note="Nison; common usage.",
    ),
    dict(
        pattern_type="morning_star",
        category="reversal",
        expected_direction="up",
        description=(
            "Three-bar: (1) large bearish bar, (2) small-body 'star' bar that gaps "
            "down, (3) large bullish bar closing above the midpoint of bar-1's body. "
            "The star marks the capitulation; bar-3 is the buyers' recovery."
        ),
        taught_expectation=(
            "Strong bullish reversal; one of the most reliable multi-bar reversal "
            "patterns in Japanese candlestick analysis. The third bar IS the action "
            "confirmation."
        ),
        confirmation_condition=(
            "The third bar's close above bar-1's midpoint IS the confirmation "
            "(built into detection). Optional additional filter: volume climax on "
            "bar-2 (panic selling) or bar-3 (demand rush)."
        ),
        invalidation_condition=(
            "If bar-3 fails to close above bar-1's midpoint at formation time, the "
            "pattern is invalid. If it forms correctly but subsequent bar closes below "
            "the pattern's low → downtrend resumes."
        ),
        invalidation_becomes=None,
        source_note=(
            "Nison; Bulkowski rates morning star as one of the highest-reliability "
            "single-reversal chart patterns."
        ),
    ),
    dict(
        pattern_type="evening_star",
        category="reversal",
        expected_direction="down",
        description=(
            "Three-bar: (1) large bullish bar, (2) small-body 'star' gapping up, "
            "(3) large bearish bar closing below bar-1's midpoint. Mirror of morning star."
        ),
        taught_expectation=(
            "Strong bearish reversal at end of uptrend. The star marks the euphoric "
            "gap; bar-3 is the sellers' capture."
        ),
        confirmation_condition=(
            "Bar-3 close below bar-1 midpoint (built into detection). Optional: "
            "volume confirmation."
        ),
        invalidation_condition=(
            "Bar-3 fails to close below bar-1 midpoint; or subsequent bar closes "
            "above the pattern's high."
        ),
        invalidation_becomes=None,
        source_note="Nison; Bulkowski.",
    ),
    dict(
        pattern_type="three_white_soldiers",
        category="continuation",
        expected_direction="up",
        description=(
            "Three consecutive bullish bars, each opening within the prior bar's body "
            "and closing near its own high, with each close making a higher level. "
            "Sustained three-session buying with orderly step-up structure."
        ),
        taught_expectation=(
            "Strong bullish signal — either continuation of an existing uptrend or a "
            "powerful recovery from a bottom. Shows persistent buyer commitment over "
            "three sessions."
        ),
        confirmation_condition=(
            "Day-4 holding above third bar's close; continued trend. Volume should "
            "ideally increase or at least not collapse."
        ),
        invalidation_condition=(
            "Day-4 bearish bar closing below third bar's midpoint — pattern exhaustion."
        ),
        invalidation_becomes=(
            "Three white soldiers followed immediately by a strong reversal bar "
            "signals CLIMACTIC BUYING EXHAUSTION → potential bearish reversal. "
            "Bulkowski notes this as a statistically common outcome after very large "
            "three-bar up-moves."
        ),
        source_note=(
            "Nison; Bulkowski (empirically mixed — continuation vs exhaustion rates "
            "are context-dependent)."
        ),
    ),
    dict(
        pattern_type="three_black_crows",
        category="continuation",
        expected_direction="down",
        description=(
            "Three consecutive bearish bars with lower closes, each opening within "
            "the prior bar's body. Sustained three-session selling."
        ),
        taught_expectation=(
            "Strong bearish signal — continuation of downtrend or powerful reversal "
            "from a top. Analogous to three white soldiers but bearish."
        ),
        confirmation_condition=(
            "Day-4 holding below third bar's close; continued downside."
        ),
        invalidation_condition=(
            "Strong bullish reversal on day-4 — doji, hammer, or strong bull bar."
        ),
        invalidation_becomes=(
            "Three black crows at an extreme low followed by a strong reversal candle "
            "signals CLIMACTIC SELLING EXHAUSTION → potential bullish reversal."
        ),
        source_note="Nison; Bulkowski.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CHART PATTERNS — detected in ta/patterns.py
    # ─────────────────────────────────────────────────────────────────────────
    dict(
        pattern_type="double_top",
        category="reversal",
        expected_direction="down",
        description=(
            "Two price peaks at approximately equal highs separated by an intervening "
            "trough (the 'neckline'). The second peak fails to exceed or materially "
            "break the first, signaling buyer exhaustion at that level."
        ),
        taught_expectation=(
            "Bearish reversal. The measured move target is the neckline minus the "
            "height of the pattern (distance from neckline to either peak). "
            "Confirms only on a close BELOW the neckline."
        ),
        confirmation_condition=(
            "Close BELOW the neckline (the trough between the two peaks). "
            "Volume typically contracts into the second peak and expands on the "
            "neckline break."
        ),
        invalidation_condition=(
            "Close ABOVE the second peak's high — buyers absorb the resistance and "
            "continue the uptrend."
        ),
        invalidation_becomes=(
            "Price breaks above the second peak AND holds on a retest of that level "
            "from above (former resistance holds as new support) → the pattern "
            "'invalidation' becomes a HIGH-QUALITY LONG CONTINUATION setup. "
            "This is one of the cleanest flip signals: trapped shorts + new buyers."
        ),
        source_note=(
            "Edwards & Magee 'Technical Analysis of Stock Trends'; Bulkowski "
            "'Encyclopedia of Chart Patterns'."
        ),
    ),
    dict(
        pattern_type="double_bottom",
        category="reversal",
        expected_direction="up",
        description=(
            "Two price troughs at approximately equal lows separated by an intervening "
            "peak (neckline). The second trough holds at or near the first, signaling "
            "persistent buyer demand at that price zone."
        ),
        taught_expectation=(
            "Bullish reversal. Measured move = neckline + height of the pattern. "
            "One of the most widely taught bullish reversal patterns."
        ),
        confirmation_condition=(
            "Close ABOVE the neckline (the peak between the two troughs). "
            "Volume usually expands on the neckline breakout."
        ),
        invalidation_condition=(
            "Close BELOW the second trough's low — support fails definitively."
        ),
        invalidation_becomes=(
            "Close below the second trough that holds on retest from below "
            "(former support holds as resistance) → SHORT continuation setup."
        ),
        source_note="Edwards & Magee; Bulkowski.",
    ),
    dict(
        pattern_type="hs_top",
        category="reversal",
        expected_direction="down",
        description=(
            "Five-pivot pattern: left shoulder (high), head (higher high), right "
            "shoulder (~equal to left shoulder). The neckline connects the two troughs "
            "between shoulders and head. The head is the highest point."
        ),
        taught_expectation=(
            "Bearish reversal; widely considered the most reliable chart reversal "
            "pattern. Measured move = neckline minus the head-to-neckline distance "
            "(the height of the head above the neckline)."
        ),
        confirmation_condition=(
            "Close BELOW the neckline. Volume typically rises on the left shoulder, "
            "is lower on the head, and lower still on the right shoulder; then "
            "expands on the neckline breakdown."
        ),
        invalidation_condition=(
            "Price re-enters above the right shoulder high after the neckline break "
            "(a 'throw-back' that holds = invalidation of the pattern)."
        ),
        invalidation_becomes=(
            "A confirmed neckline break that fails and reverses above the right "
            "shoulder — rare but meaningful. Usually resumes with a complex "
            "re-distribution top rather than a clean flip; no single textbook signal."
        ),
        source_note=(
            "Edwards & Magee (described as 'most reliable of all chart formations'); "
            "Bulkowski; Murphy 'Technical Analysis of the Financial Markets'."
        ),
    ),
    dict(
        pattern_type="hs_bottom",
        category="reversal",
        expected_direction="up",
        description=(
            "Inverse head-and-shoulders: left shoulder (low), head (lower low), right "
            "shoulder (~equal to left). Neckline connects the two peaks between them."
        ),
        taught_expectation=(
            "Bullish reversal. Measured move = neckline plus the neckline-to-head "
            "distance. Often forms after sustained downtrends."
        ),
        confirmation_condition=(
            "Close ABOVE the neckline, ideally with volume expansion."
        ),
        invalidation_condition=(
            "Price drops back below the right shoulder low."
        ),
        invalidation_becomes=None,
        source_note="Edwards & Magee; Bulkowski; Murphy.",
    ),
    dict(
        pattern_type="bull_flag",
        category="continuation",
        expected_direction="up",
        description=(
            "Rapid up-move (the 'pole', typically ≥8% in ≤25 bars) followed by a "
            "tight, slightly downward or sideways consolidation (the 'flag'). The "
            "consolidation retraces only a fraction of the pole."
        ),
        taught_expectation=(
            "Bullish continuation. Measured move = flag breakout point + pole height "
            "(repeat the pole). The flag represents controlled distribution before "
            "the next leg up."
        ),
        confirmation_condition=(
            "Close ABOVE the upper boundary of the flag (above the pole top). "
            "Volume typically contracts during the flag and expands on the breakout."
        ),
        invalidation_condition=(
            "Close BELOW the lower boundary of the flag (below the flag's trough)."
        ),
        invalidation_becomes=(
            "A close below the flag that then accelerates lower is one of the strongest "
            "SHORT signals available: the 'failed bull flag.' Trapped bulls exit, "
            "accelerating the move. Measured target = flag breakdown minus pole height."
        ),
        source_note=(
            "Bulkowski 'Trading Classic Chart Patterns'; Edwards & Magee; "
            "O'Neil 'How to Make Money in Stocks' (CANSLIM — flags are a core entry signal)."
        ),
    ),
    dict(
        pattern_type="bear_flag",
        category="continuation",
        expected_direction="down",
        description=(
            "Rapid down-move (pole) followed by a tight slightly upward or sideways "
            "consolidation. Consolidation retraces only part of the pole."
        ),
        taught_expectation=(
            "Bearish continuation. Measured move = breakdown level minus pole height."
        ),
        confirmation_condition=(
            "Close BELOW the lower boundary of the bear flag. Volume contracts "
            "during flag, expands on breakdown."
        ),
        invalidation_condition=(
            "Close ABOVE the top of the flag / pole top."
        ),
        invalidation_becomes=(
            "Failed bear flag (close above flag top + acceleration) → strong LONG "
            "signal. Trapped shorts cover, adding fuel."
        ),
        source_note="Bulkowski; Edwards & Magee; O'Neil.",
    ),
    dict(
        pattern_type="swing_leg",
        category="context",
        expected_direction="n/a",
        description=(
            "A structural measurement of a discrete price swing from a defined pivot "
            "low to a defined pivot high. Captures amplitude, duration, early-bar "
            "slope, and subsequent correction depth. Not a trade signal — a "
            "feature-engineering primitive for research."
        ),
        taught_expectation=(
            "No textbook directional expectation. The swing_leg is a descriptor: "
            "given the early signature of a move (slope, first-N-bar gain), what can "
            "be inferred about where price goes next? This is the research question, "
            "not a pre-coded answer. The fulfillment backtest answers this empirically."
        ),
        confirmation_condition="N/A — structural descriptor, not a signal.",
        invalidation_condition="N/A",
        invalidation_becomes=None,
        source_note=(
            "Internal research construct. Conceptually related to Edwards & Magee "
            "swing-measurement principles, but the dome/early-slope form is proprietary."
        ),
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CHANNEL PATTERNS — detected in ta/channels.py (feat/channels-and-5m)
    # ─────────────────────────────────────────────────────────────────────────
    dict(
        pattern_type="channel_ascending",
        category="bilateral",
        expected_direction="bidirectional",
        description=(
            "Price bounded between two rising parallel trendlines — a support line "
            "through swing lows and a resistance line through swing highs, both sloping "
            "upward at approximately the same angle."
        ),
        taught_expectation=(
            "Primarily a continuation pattern within an existing uptrend. Price "
            "expected to 'bounce' within the channel. However, direction of the "
            "resolution depends entirely on which boundary breaks: a breakout above "
            "the upper line signals acceleration higher; a breakdown below the lower "
            "line signals a trend reversal."
        ),
        confirmation_condition=(
            "For bullish continuation: bounce off the lower channel support line with "
            "a bullish candle. For a breakout: close above the upper trendline with "
            "expanded volume. For a breakdown: close below the lower support line."
        ),
        invalidation_condition=(
            "Close below the lower channel support — channel structure is violated."
        ),
        invalidation_becomes=(
            "Close below lower channel support → trend reversal; prior support becomes "
            "resistance on a retest from below → SHORT setup."
        ),
        source_note=(
            "Edwards & Magee; Murphy 'Technical Analysis of the Financial Markets'; "
            "also called a 'rising channel' or 'bullish regression channel'."
        ),
    ),
    dict(
        pattern_type="channel_descending",
        category="bilateral",
        expected_direction="bidirectional",
        description=(
            "Two falling parallel trendlines — both swing highs and swing lows making "
            "lower levels at approximately the same rate, forming a declining channel."
        ),
        taught_expectation=(
            "Primarily bearish continuation within a downtrend. Price bounces between "
            "descending support and resistance. Breakout above the upper line is a "
            "potential trend reversal to the upside."
        ),
        confirmation_condition=(
            "For bearish continuation: bounce off upper channel resistance with a "
            "bearish candle. For a breakout: close above upper trendline."
        ),
        invalidation_condition=(
            "Close above upper channel resistance — bearish structure violated."
        ),
        invalidation_becomes=(
            "Close above upper channel → bullish trend reversal; prior resistance "
            "becomes support on retest → LONG setup."
        ),
        source_note="Edwards & Magee; Murphy.",
    ),
    dict(
        pattern_type="channel_horizontal",
        category="bilateral",
        expected_direction="bidirectional",
        description=(
            "Price oscillating between two approximately horizontal parallel trendlines "
            "— a trading range where neither bulls nor bears establish directional "
            "control. Also called a 'rectangle' pattern."
        ),
        taught_expectation=(
            "No inherent directional bias — the channel itself is neutral. The "
            "actionable event is a BREAKOUT in either direction. Textbook literature "
            "is genuinely bilateral: a close above resistance → long; a close below "
            "support → short."
        ),
        confirmation_condition=(
            "Close clearly above the resistance line (bullish breakout) or below the "
            "support line (bearish breakdown)."
        ),
        invalidation_condition=(
            "Price immediately reverses back inside the channel after an apparent break "
            "(false breakout)."
        ),
        invalidation_becomes=(
            "A false bull breakout (back below resistance after one bar) → BEAR "
            "TRAP: trapped longs exit → SHORT signal. "
            "A false bear breakdown → BULL TRAP: trapped shorts cover → LONG signal."
        ),
        source_note=(
            "Edwards & Magee ('rectangles'); Murphy; Bulkowski."
        ),
    ),
    dict(
        pattern_type="channel_break",
        category="bilateral",
        expected_direction="bidirectional",
        description=(
            "The confirmed breakout event FROM a channel (ascending, descending, or "
            "horizontal) at the bar where price closes beyond the channel boundary. "
            "Direction is encoded in the pattern_memory direction field."
        ),
        taught_expectation=(
            "Directional continuation in the direction of the break. Measured move = "
            "width of the channel, added (bull break) or subtracted (bear break) from "
            "the breakout point. Volume expansion on the break bar strengthens the signal."
        ),
        confirmation_condition=(
            "The close outside the channel IS the primary signal. A subsequent bar "
            "that retests the broken boundary and holds (old resistance as support, or "
            "vice versa) is the strongest secondary confirmation."
        ),
        invalidation_condition=(
            "Price immediately re-enters the channel (closes back inside) within 1-2 "
            "bars — a 'false break' or 'spring'."
        ),
        invalidation_becomes=(
            "A false break back inside the channel is a strong signal in the OPPOSITE "
            "direction ('bull trap' or 'bear trap'): trapped breakout traders exit, "
            "adding momentum to the reversal."
        ),
        source_note=(
            "Edwards & Magee; Murphy; Bulkowski. "
            "System writes channel_break at the bar the close crosses the channel boundary."
        ),
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # TA CONTEXT TOOLS — computed separately (not in pattern_memory rows)
    # pattern_type names chosen to match system conventions
    # ─────────────────────────────────────────────────────────────────────────
    dict(
        pattern_type="vwap",
        category="context",
        expected_direction="n/a",
        description=(
            "Session-anchored Volume-Weighted Average Price (vwap_5m table). Resets "
            "daily at the open. Represents the average price at which all shares "
            "traded during the session, weighted by volume at each bar."
        ),
        taught_expectation=(
            "Intraday directional benchmark. Price consistently above VWAP = bulls in "
            "control (institutional buying); price consistently below = bears. "
            "VWAP is not a signal itself — it's a contextual state. A 'VWAP reclaim' "
            "(price returning above VWAP from below) is used as an intraday long setup; "
            "a 'VWAP rejection' (failing to hold above) is a short setup."
        ),
        confirmation_condition=(
            "VWAP reclaim long: close back above VWAP and hold for 1-2 bars. "
            "VWAP rejection short: close back below VWAP after a failed attempt."
        ),
        invalidation_condition=(
            "For a VWAP reclaim long: immediate return below VWAP within 1 bar."
        ),
        invalidation_becomes=None,
        source_note=(
            "VWAP originated in institutional trading (Treynor, 1987); widely "
            "described in Kahn 'Technical Analysis Plain and Simple'; standard "
            "intraday benchmark for execution quality."
        ),
    ),
    dict(
        pattern_type="classic_gap_up",
        category="context",
        expected_direction="up",
        description=(
            "Today's open exceeds yesterday's high, leaving an entirely untraded price "
            "zone between yesterday's high and today's open. Stored in the gaps table "
            "with gap_type='classic', direction='up'."
        ),
        taught_expectation=(
            "Often bullish continuation (large gaps frequently hold and continue). "
            "However, gap-fills (price returning to the gap zone) occur frequently "
            "within days to weeks. Context matters heavily: a gap in a strong uptrend "
            "is different from an exhaustion gap at extended valuations."
        ),
        confirmation_condition=(
            "Gap holds at end of the session (price does not fill). On a pullback, "
            "the top of the gap zone (yesterday's high) holds as support."
        ),
        invalidation_condition=(
            "Price fills the gap zone within the same session (gaps back below "
            "yesterday's high)."
        ),
        invalidation_becomes=(
            "Same-session gap fill + close below yesterday's high → 'exhaustion gap' "
            "reversal signal → bearish."
        ),
        source_note=(
            "Bulkowski 'Trading Classic Chart Patterns'; Murphy. "
            "Classic gaps (daily timeframe) in the gaps table."
        ),
    ),
    dict(
        pattern_type="classic_gap_down",
        category="context",
        expected_direction="down",
        description=(
            "Today's open below yesterday's low, leaving an untraded price zone. "
            "Stored in the gaps table with gap_type='classic', direction='down'."
        ),
        taught_expectation=(
            "Often bearish continuation, but many gap-downs are 'reaction gaps' that "
            "fill within days as panic subsides. Catalyst-driven gap-downs (earnings, "
            "macro) are more likely to hold."
        ),
        confirmation_condition=(
            "Gap holds intraday; first bounce to the gap zone (yesterday's low) acts "
            "as resistance."
        ),
        invalidation_condition=(
            "Same-session gap fill (price rallies back above yesterday's low)."
        ),
        invalidation_becomes=(
            "Full gap fill + close above yesterday's low → buyers absorbed all the "
            "selling → bullish reversal signal."
        ),
        source_note="Bulkowski; Murphy.",
    ),
    dict(
        pattern_type="fvg_bullish",
        category="context",
        expected_direction="up",
        description=(
            "Fair Value Gap (bullish). Three-bar imbalance where bar-1's high is "
            "entirely below bar-3's low — an untraded price zone between them. "
            "Stored in gaps table with gap_type='fvg', direction='up'. "
            "Also called a '3-bar imbalance' or 'inefficiency' in SMC / ICT analysis."
        ),
        taught_expectation=(
            "The FVG zone is expected to act as support on a subsequent pullback. "
            "Price often 'returns to fill' the zone to rebalance the imbalance, then "
            "either holds (bullish continuation) or breaks through (invalidated). "
            "The zone is treated as a high-probability long entry area on the retest."
        ),
        confirmation_condition=(
            "Price enters the FVG zone and a bullish reaction occurs: close above "
            "the zone's bottom (bar-1 high = zone_bottom). Ideally a bullish reversal "
            "candle forms inside the zone."
        ),
        invalidation_condition=(
            "Price closes BELOW the zone_bottom (below bar-1's high) after entering "
            "the zone — the zone is 'filled and broken'."
        ),
        invalidation_becomes=(
            "FVG filled and broken: zone that was support becomes resistance. "
            "The next retest of the zone from below → SHORT setup."
        ),
        source_note=(
            "Smart Money Concepts (SMC) / ICT (Inner Circle Trader) methodology; "
            "non-classical but widely cited in retail TA as of 2020s."
        ),
    ),
    dict(
        pattern_type="fvg_bearish",
        category="context",
        expected_direction="down",
        description=(
            "Fair Value Gap (bearish). Three-bar imbalance where bar-1's low is "
            "entirely above bar-3's high — untraded zone between bar-3's high and "
            "bar-1's low. Stored in gaps table with gap_type='fvg', direction='down'."
        ),
        taught_expectation=(
            "The FVG zone acts as resistance on a subsequent bounce. Price expected "
            "to return and rebalance, then continue lower or break through."
        ),
        confirmation_condition=(
            "Price bounces into the zone and a bearish reaction: close below "
            "zone_top (bar-1's low) after entering."
        ),
        invalidation_condition=(
            "Price closes ABOVE zone_top after entering the zone — zone is filled "
            "and broken."
        ),
        invalidation_becomes=(
            "FVG filled and broken: was resistance, now support. "
            "Retest of zone from above → LONG setup."
        ),
        source_note="SMC / ICT methodology.",
    ),
    dict(
        pattern_type="omni_82",
        category="context",
        expected_direction="n/a",
        description=(
            "EMA of daily LOW prices, period 82 (Oscar Carboni's OMNI indicator). "
            "Computed in features/omni_proxy.py. Tracks candle bottoms rather than "
            "closes — hugs the lower bounds of price action more closely than a "
            "traditional close-based EMA."
        ),
        taught_expectation=(
            "Acts as a dynamic support line in uptrends. When price is above OMNI-82 "
            "and the indicator is rising (green slope), the trend is healthy. "
            "Cross of close below OMNI-82 signals potential trend breakdown. "
            "A bounce off OMNI-82 with a bullish close bar (omni_82_bounce) is the "
            "primary long-entry signal. 81.9% 20-day hit rate on SPY cross-up signals "
            "(2011-2026, per internal backtest)."
        ),
        confirmation_condition=(
            "Cross-up: close crosses above OMNI-82 after being below (omni_82_cross_up). "
            "Bounce: low touches within 0.5% of OMNI-82, bar closes bullish."
        ),
        invalidation_condition=(
            "Cross-down: close crosses below OMNI-82 (omni_82_cross_down). "
            "Slope turning negative while price is below."
        ),
        invalidation_becomes=(
            "Cross below OMNI-82 on rising-slope indicator followed by failure to "
            "reclaim → intermediate-term trend breakdown → bearish bias."
        ),
        source_note=(
            "Oscar Carboni (TV commentator) OMNI system; confirmed as EMA(Low, 82) "
            "via internal reverse-engineering (see features/omni_proxy.py). "
            "81.9% hit rate is internal empirical result, not from Carboni."
        ),
    ),
    dict(
        pattern_type="oscar_87",
        category="context",
        expected_direction="bidirectional",
        description=(
            "OSCAR oscillator, 87-period (computed in features/omni_proxy.py). "
            "Smoothed stochastic: A=max(High,N), B=min(Low,N), rough=(Close-B)/(A-B)*100, "
            "oscar = prev*2/3 + rough*1/3. Oscillates 0-100."
        ),
        taught_expectation=(
            "Trend oscillator. Cross above 50 → bullish bias; cross below 50 → bearish. "
            "Values near 0 = potential bottom; near 100 = potential top. "
            "Not an overbought/oversold indicator in the RSI sense — it tracks "
            "where price sits within its recent range."
        ),
        confirmation_condition=(
            "Cross above 50 (oscar_cross_up) with OMNI-82 in uptrend = strong bull. "
            "Cross below 50 (oscar_cross_down) with OMNI-82 in downtrend = strong bear."
        ),
        invalidation_condition=(
            "Cross in the expected direction immediately reverses back across 50."
        ),
        invalidation_becomes=None,
        source_note=(
            "Oscar Carboni OSCAR oscillator formula; implemented in features/omni_proxy.py."
        ),
    ),
    dict(
        pattern_type="rsi",
        category="context",
        expected_direction="bidirectional",
        description=(
            "Relative Strength Index (14-period standard). Momentum oscillator "
            "comparing average gains to average losses over N periods. Stored in "
            "pattern_memory.rsi column."
        ),
        taught_expectation=(
            "RSI > 70 = potentially overbought (stretched, not necessarily reversal). "
            "RSI < 30 = potentially oversold. More valuable as a divergence indicator "
            "(price makes new high but RSI doesn't = bearish divergence, and vice versa). "
            "RSI < 30 followed by a cross back above 30 ('RSI reclaim') is a widely "
            "used re-entry trigger."
        ),
        confirmation_condition=(
            "Bearish: RSI crosses back below 70 after being overbought (confirms "
            "reversal). Bullish: RSI crosses back above 30 (RSI reclaim)."
        ),
        invalidation_condition=(
            "In strong trends, RSI can remain overbought (>70) or oversold (<30) for "
            "extended periods — fade signals can be extremely costly in trending markets."
        ),
        invalidation_becomes=None,
        source_note=(
            "Wilder 'New Concepts in Technical Trading Systems' (1978); "
            "standard in every TA reference."
        ),
    ),
    dict(
        pattern_type="macd",
        category="context",
        expected_direction="bidirectional",
        description=(
            "MACD histogram (fast_ema - slow_ema - signal_line). Standard params: "
            "EMA(12) - EMA(26) - EMA(9) of the difference. Stored in "
            "pattern_memory.macd_hist column."
        ),
        taught_expectation=(
            "Histogram above zero = bullish momentum; below = bearish. "
            "Rising histogram = increasing momentum in direction; falling = fading. "
            "A zero-line cross (MACD line crosses above/below signal) is a trade trigger. "
            "Divergence (price vs MACD histogram) is a leading reversal signal."
        ),
        confirmation_condition=(
            "Bullish: MACD line crosses above signal line (positive histogram). "
            "Zero-line cross (histogram crosses from - to +). "
            "Bearish: reverse."
        ),
        invalidation_condition=(
            "Signal cross immediately reverses — 'whipsaw.' "
            "Common in choppy/range-bound markets."
        ),
        invalidation_becomes=None,
        source_note=(
            "Gerald Appel (1970s); documented in Murphy; "
            "ubiquitous in modern technical analysis."
        ),
    ),
    dict(
        pattern_type="adx",
        category="context",
        expected_direction="n/a",
        description=(
            "Average Directional Index (14-period). Measures TREND STRENGTH, not "
            "direction. ADX > 25 = trending market; > 40 = strong trend; < 20 = ranging. "
            "Stored in pattern_memory.adx column."
        ),
        taught_expectation=(
            "Not directional by itself — only measures trend strength. "
            "High ADX with RSI or MACD trend-aligned = high-confidence directional bet. "
            "Low ADX = avoid trend-following strategies; use mean-reversion. "
            "Rising ADX = trend strengthening; falling ADX from high levels = trend fading."
        ),
        confirmation_condition=(
            "ADX > 25 rising + positive DI crossover (when available) = confirming trend. "
        ),
        invalidation_condition=(
            "ADX begins falling from > 30 = trend exhausting; "
            "trend-following signals become less reliable."
        ),
        invalidation_becomes=None,
        source_note=(
            "Wilder 'New Concepts in Technical Trading Systems' (1978); "
            "standard trend-strength indicator."
        ),
    ),
    dict(
        pattern_type="atr",
        category="context",
        expected_direction="n/a",
        description=(
            "Average True Range (14-period). Measures volatility as the average of "
            "true ranges (max(high,prev_close) - min(low,prev_close)). Stored in "
            "pattern_memory.atr_pct column as a percentage of price."
        ),
        taught_expectation=(
            "Volatility context only — not directional. "
            "High ATR% = wide ranges, suitable for wider stops and targets. "
            "Low ATR% = compression, potential breakout setup building. "
            "ATR is the standard position-sizing input: size = risk_per_trade / ATR."
        ),
        confirmation_condition="N/A — pure volatility context.",
        invalidation_condition="N/A",
        invalidation_becomes=None,
        source_note=(
            "Wilder 'New Concepts in Technical Trading Systems' (1978); "
            "universal in quantitative position sizing."
        ),
    ),
    dict(
        pattern_type="volume_ratio",
        category="context",
        expected_direction="n/a",
        description=(
            "Ratio of current bar's volume to recent average volume (pattern_memory."
            "vol_ratio column). vol_ratio > 1 = above-average volume; < 1 = below-average."
        ),
        taught_expectation=(
            "Volume amplifies price signals. High volume on a breakout or reversal "
            "candle increases its reliability. Low volume during consolidation is "
            "normal and expected. Volume divergence (price makes new high on lower "
            "volume) is a potential exhaustion warning."
        ),
        confirmation_condition=(
            "For any directional signal: vol_ratio > 1.5 on the signal bar is "
            "confirmatory. vol_ratio > 2.0 = significant institutional participation."
        ),
        invalidation_condition=(
            "Breakout on vol_ratio < 0.8 = weak, higher probability of false break."
        ),
        invalidation_becomes=None,
        source_note=(
            "Murphy; Wyckoff (volume as the 'effort' component in effort-vs-result); "
            "O'Neil (volume expansion key for CANSLIM buy points)."
        ),
    ),
    dict(
        pattern_type="sma_stack",
        category="context",
        expected_direction="n/a",
        description=(
            "SMA alignment: whether SMA-50 > SMA-150 > SMA-200 (sma_stacked=TRUE in "
            "pattern_memory). Represents an 'ideal' long-term trend alignment where "
            "shorter-period moving averages are stacked above longer-period ones."
        ),
        taught_expectation=(
            "When sma_stacked=TRUE (50>150>200 all sloping up), the stock is in a "
            "strong long-term uptrend. This is the Mark Minervini / O'Neil 'VCP "
            "template' prerequisite: all pattern breakouts are more reliable in this "
            "context. Inverse stacking (50<150<200 all descending) = downtrend regime."
        ),
        confirmation_condition=(
            "All three SMAs sloping upward and stacked 50>150>200. "
            "Price above SMA-200 (dist_sma200 > 0) adds confirmation."
        ),
        invalidation_condition=(
            "SMA-50 crossing below SMA-150 breaks the stacking — intermediate-term "
            "deterioration. More serious: SMA-50 crossing below SMA-200 (death cross)."
        ),
        invalidation_becomes=(
            "Stack inversion (50 < 150 < 200) → confirmed downtrend regime. "
            "Golden cross (50 > 200) → beginning of potential uptrend regime recovery."
        ),
        source_note=(
            "Minervini 'Trade Like a Stock Market Wizard' (VCP / stage analysis); "
            "O'Neil; Stan Weinstein 'Secrets for Profiting in Bull and Bear Markets' "
            "(Stage 2 uptrend requires SMAs stacked and rising)."
        ),
    ),
]


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)

    upsert = text("""
        INSERT INTO pattern_reference (
            pattern_type, category, expected_direction, description,
            taught_expectation, confirmation_condition, invalidation_condition,
            invalidation_becomes, source_note
        )
        VALUES (
            :pattern_type, :category, :expected_direction, :description,
            :taught_expectation, :confirmation_condition, :invalidation_condition,
            :invalidation_becomes, :source_note
        )
        ON CONFLICT (pattern_type) DO UPDATE SET
            category               = EXCLUDED.category,
            expected_direction     = EXCLUDED.expected_direction,
            description            = EXCLUDED.description,
            taught_expectation     = EXCLUDED.taught_expectation,
            confirmation_condition = EXCLUDED.confirmation_condition,
            invalidation_condition = EXCLUDED.invalidation_condition,
            invalidation_becomes   = EXCLUDED.invalidation_becomes,
            source_note            = EXCLUDED.source_note
    """)

    with engine.begin() as conn:
        for row in ROWS:
            conn.execute(upsert, row)

    print(f"Seeded {len(ROWS)} rows into pattern_reference.")

    # Verification
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM pattern_reference")).scalar()
        cats = conn.execute(text(
            "SELECT category, COUNT(*) FROM pattern_reference GROUP BY category ORDER BY category"
        )).fetchall()
        dirs = conn.execute(text(
            "SELECT expected_direction, COUNT(*) FROM pattern_reference "
            "GROUP BY expected_direction ORDER BY expected_direction"
        )).fetchall()
        missing_source = conn.execute(text(
            "SELECT pattern_type FROM pattern_reference WHERE source_note IS NULL ORDER BY pattern_type"
        )).fetchall()
        null_invalidation = conn.execute(text(
            "SELECT pattern_type FROM pattern_reference WHERE invalidation_becomes IS NULL ORDER BY 1"
        )).fetchall()

    print(f"\nTotal rows: {total}")
    print("\nBy category:")
    for r in cats:
        print(f"  {r[0]:<15} {r[1]:>3}")
    print("\nBy expected_direction:")
    for r in dirs:
        print(f"  {r[0]:<25} {r[1]:>3}")
    print(f"\nRows with invalidation_becomes=NULL: {len(null_invalidation)}")
    print(f"Rows with source_note=NULL: {len(missing_source)}")


if __name__ == "__main__":
    main()
