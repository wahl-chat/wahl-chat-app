'use server';

import { getWahlSwiperTheses } from '@/lib/firebase/firebase-server';
import type {
  PartiesScoreResult,
  WahlSwiperResultHistory,
} from './wahl-swiper.types';

export async function wahlSwiperCalculateScore(
  userResponses: WahlSwiperResultHistory,
) {
  const theses = await getWahlSwiperTheses();

  const scores: PartiesScoreResult = {};
  const filteredUserResponses = Object.fromEntries(
    Object.entries(userResponses).filter(([, value]) => value !== 'skip'),
  );
  const totalQuestions = Object.keys(filteredUserResponses).length;

  // Return empty scores if all questions were skipped
  if (totalQuestions === 0) {
    return {};
  }

  for (const thesis of theses) {
    if (!(thesis.id in filteredUserResponses)) continue;

    const userStance = filteredUserResponses[thesis.id];

    if (userStance === 'skip') continue;

    for (const position of thesis.positions) {
      if (!(position.party_id in scores)) {
        scores[position.party_id] = {
          score: 0,
          theses: [],
        };
      }

      if (position.stance === userStance) {
        scores[position.party_id].score += 1;
      }

      scores[position.party_id].theses.push({
        consensus: userStance === position.stance,
        userStance,
        partyStance: position.stance,
        thesis: {
          id: thesis.id,
          topic: thesis.topic,
          question: thesis.question,
        },
      });
    }
  }

  // Convert scores to percentages
  for (const party in scores) {
    scores[party].score = (scores[party].score / totalQuestions) * 100;
  }

  return scores;
}
