/*
 * Cyberpunk TCG - TCG Arena Gameplay Engine
 *
 * Engine version: 0.1
 *
 * Current Beta rules foundation:
 * - Start Phase
 * - Main Phase
 * - Player state
 * - Once-per-turn state
 * - Gig state helpers
 * - Street Cred
 * - Victory detection
 *
 * This file intentionally does NOT implement card-specific effects yet.
 */

const CYBERPUNK_ENGINE_VERSION = "0.1.0";

/* =========================================================
 * GENERAL HELPERS
 * ========================================================= */

function cpLog(message) {
    if (typeof chatLog === "function") {
        chatLog("[Cyberpunk] " + message);
    }
}

function cpNumber(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}

/* =========================================================
 * PLAYER STATE
 * ========================================================= */

function cpCreatePlayerState() {
    return {
        eddies: 0,

        soldThisTurn: false,
        calledLegendThisTurn: false,

        streetCred: 0,
        gigCount: 0
    };
}

/* =========================================================
 * GAME STATE
 * ========================================================= */

function cpCreateGameState() {
    return {
        version: CYBERPUNK_ENGINE_VERSION,

        initialized: true,

        turn: {
            number: 1,
            phase: "START"
        },

        players: {
            my: cpCreatePlayerState(),
            opponent: cpCreatePlayerState()
        },

        combat: {
            active: false,
            attacker: null,
            target: null,
            reactionWindow: false,
            blocker: null
        },

        overtime: false,
        gameOver: false,
        winner: null
    };
}

/*
 * Initialise the Cyberpunk game state if it doesn't exist.
 */
function cpEnsureState() {
    if (!game.data.cyberpunk) {
        game.data.cyberpunk = cpCreateGameState();
        cpLog("Game engine initialised.");
    }

    return game.data.cyberpunk;
}

/* =========================================================
 * GIG HELPERS
 * ========================================================= */

/*
 * Return the player's current controlled Gigs.
 *
 * A die belongs to the player when:
 * - it is their own die and has not been stolen
 * - OR it is an opponent die that has been stolen
 */
function cpGetMyGigs() {
    const state = cpEnsureState();

    const own = game.data.MyGigs?.dices || [];
    const stolen = game.data.OppGigs?.dices || [];

    return [
        ...own.filter(die => !die.stolen && cpNumber(die.value) > 0),
        ...stolen.filter(die => die.stolen && cpNumber(die.value) > 0)
    ];
}

function cpGetOpponentGigs() {
    const own = game.data.OppGigs?.dices || [];
    const stolen = game.data.MyGigs?.dices || [];

    return [
        ...own.filter(die => !die.stolen && cpNumber(die.value) > 0),
        ...stolen.filter(die => die.stolen && cpNumber(die.value) > 0)
    ];
}

/*
 * Number of Gigs currently controlled.
 */
function cpGetMyGigCount() {
    return cpGetMyGigs().length;
}

function cpGetOpponentGigCount() {
    return cpGetOpponentGigs().length;
}

/*
 * Street Cred is the sum of the face values of all
 * Gig dice currently controlled by the player.
 */
function cpGetMyStreetCred() {
    return cpGetMyGigs().reduce(
        (total, die) => total + cpNumber(die.value),
        0
    );
}

function cpGetOpponentStreetCred() {
    return cpGetOpponentGigs().reduce(
        (total, die) => total + cpNumber(die.value),
        0
    );
}

/*
 * Synchronise derived Gig values into our engine state.
 */
function cpUpdateGigState() {
    const state = cpEnsureState();

    state.players.my.gigCount = cpGetMyGigCount();
    state.players.my.streetCred = cpGetMyStreetCred();

    state.players.opponent.gigCount = cpGetOpponentGigCount();
    state.players.opponent.streetCred = cpGetOpponentStreetCred();

    return state;
}

/* =========================================================
 * TURN STATE
 * ========================================================= */

function cpSetPhase(phase) {
    const state = cpEnsureState();

    state.turn.phase = phase;

    cpLog("Phase: " + phase);
}

function cpStartTurn() {
    const state = cpEnsureState();

    state.turn.phase = "START";

    state.players.my.soldThisTurn = false;
    state.players.my.calledLegendThisTurn = false;

    state.players.opponent.soldThisTurn = false;
    state.players.opponent.calledLegendThisTurn = false;

    cpUpdateGigState();

    cpCheckVictory();

    if (!state.gameOver) {
        cpLog("Start Phase.");
    }
}

function cpEnterMainPhase() {
    const state = cpEnsureState();

    if (state.gameOver) {
        return;
    }

    state.turn.phase = "MAIN";

    cpLog("Main Phase.");
}

function cpEndTurn() {
    const state = cpEnsureState();

    if (state.gameOver) {
        return;
    }

    cpUpdateGigState();

    state.turn.number += 1;

    cpStartTurn();
}

/* =========================================================
 * ONCE-PER-TURN ACTIONS
 * ========================================================= */

function cpCanSell() {
    const state = cpEnsureState();

    return !state.players.my.soldThisTurn;
}

function cpMarkSold() {
    const state = cpEnsureState();

    state.players.my.soldThisTurn = true;
}

function cpCanCallLegend() {
    const state = cpEnsureState();

    return !state.players.my.calledLegendThisTurn;
}

function cpMarkLegendCalled() {
    const state = cpEnsureState();

    state.players.my.calledLegendThisTurn = true;
}

/* =========================================================
 * COMBAT STATE
 * ========================================================= */

function cpBeginAttack(attackerId, target) {
    const state = cpEnsureState();

    if (state.gameOver) {
        return false;
    }

    state.combat.active = true;
    state.combat.attacker = attackerId;
    state.combat.target = target;
    state.combat.reactionWindow = false;
    state.combat.blocker = null;

    return true;
}

function cpBeginReactionWindow() {
    const state = cpEnsureState();

    if (!state.combat.active) {
        return;
    }

    state.combat.reactionWindow = true;
}

function cpEndAttack() {
    const state = cpEnsureState();

    state.combat.active = false;
    state.combat.attacker = null;
    state.combat.target = null;
    state.combat.reactionWindow = false;
    state.combat.blocker = null;
}

/* =========================================================
 * VICTORY
 * ========================================================= */

function cpCheckVictory() {
    const state = cpUpdateGigState();

    /*
     * Current Beta rule:
     * Start your turn with 7 or more Gigs to win.
     */
    if (
        state.turn.phase === "START" &&
        state.players.my.gigCount >= 7
    ) {
        state.gameOver = true;
        state.winner = "my";

        cpLog("YOU WIN — you started your turn with 7 Gigs.");
        return true;
    }

    if (
        state.turn.phase === "START" &&
        state.players.opponent.gigCount >= 7
    ) {
        state.gameOver = true;
        state.winner = "opponent";

        cpLog("RIVAL WINS — they started their turn with 7 Gigs.");
        return true;
    }

    return false;
}

/* =========================================================
 * DEBUG / TEST HELPERS
 * ========================================================= */

/*
 * Useful during development.
 * These do not implement game rules themselves.
 */

function cpDebugState() {
    const state = cpUpdateGigState();

    cpLog(
        "Turn " +
        state.turn.number +
        " | Phase " +
        state.turn.phase +
        " | My Gigs " +
        state.players.my.gigCount +
        " | My Street Cred " +
        state.players.my.streetCred +
        " | Eddies " +
        state.players.my.eddies
    );

    return state;
}

/* =========================================================
 * INITIALISE
 * ========================================================= */

cpEnsureState();
cpUpdateGigState();