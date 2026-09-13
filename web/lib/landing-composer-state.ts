export type LandingComposerState = {
  contextId: string;
  question: string;
  partyIds: string[];
  focusRequest: number;
};

export type LandingComposerAction =
  | { type: 'question'; question: string }
  | { type: 'context'; contextId: string }
  | { type: 'parties'; partyIds: string[] }
  | { type: 'suggestion'; contextId: string; question: string };

export function landingComposerReducer(
  state: LandingComposerState,
  action: LandingComposerAction,
): LandingComposerState {
  switch (action.type) {
    case 'question':
      return { ...state, question: action.question.slice(0, 500) };
    case 'parties':
      return { ...state, partyIds: action.partyIds };
    case 'context':
      if (state.contextId === action.contextId) return state;
      // Party IDs belong to an election; the user's draft does not.
      return { ...state, contextId: action.contextId, partyIds: [] };
    case 'suggestion':
      return {
        ...state,
        contextId: action.contextId,
        question: action.question.slice(0, 500),
        partyIds: state.contextId === action.contextId ? state.partyIds : [],
        focusRequest: state.focusRequest + 1,
      };
  }
}
