export type WahlSwiperQuestion = {
  id: string;
  title: string;
  statement: string;
  question: string;
  topic: string;
  positions: PartyPosition[];
};

type PartyPosition = {
  party_id: string;
  party_short: string;
  party_name: string;
  stance: 'yes' | 'no';
  justification: string | null;
};

export type SwipeType = 'yes' | 'no' | 'skip';

export type ResultType = { [k in SwipeType]: number };

export type HistoryType = { id: string; swipe: SwipeType };

export type PartiesScoreResult = {
  [party_id: string]: {
    score: number;
    theses: ThesesScoreResult;
  };
};

export type ThesesScoreResult = {
  consensus: boolean;
  userStance: SwipeType;
  partyStance: 'yes' | 'no';
  thesis: {
    id: string;
    topic: string;
    question: string;
  };
}[];

export type WahlSwiperResultHistory = Record<string, SwipeType>;
