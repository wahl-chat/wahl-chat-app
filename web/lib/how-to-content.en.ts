import { MAX_SELECTABLE_PARTIES } from '@/lib/constants';
import type { HowToContent } from '@/lib/how-to-content';

const PARTY_SPECIFIC_QUESTIONS = [
  "What is the SPD's position on climate protection?",
  "What is the AfD's stance on the debt brake?",
  'How does the CDU/CSU want to cut red tape?',
  'How do the Greens want to drive digitalisation forward?',
  'How do the FDP and Die Linke want to implement working-time reform?',
  'How do Volt and the FDP want to improve European cooperation?',
];

const COMPARE_QUESTIONS = [
  'How do the parties differ in tackling climate change?',
  'How do the positions of the CDU/CSU and the SPD differ on the debt brake?',
  'Compare the positions of the FDP and the AfD on migration.',
];

const GENERAL_QUESTIONS = [
  'How do I apply for a postal vote?',
  'Who is behind wahl.chat?',
  'How does postal voting work?',
];

export const HOW_TO_EN: HowToContent = {
  introText: {
    main: "wahl.chat is an interactive AI tool that helps you find out about the parties' positions and plans. You can ask the AI assistant questions on all kinds of political topics, and it gives you neutral answers based on the parties' manifestos and other publications.",
    sources:
      'Every answer comes with its sources and draws on the documents relevant to the election you have selected.',
  },

  processSteps: [
    'You ask a question',
    'wahl.chat searches relevant documents such as election manifestos and party programmes to find the right information.',
    'That information is then used to generate a clear answer backed by sources.',
    "You can now have the party's position put into context by clicking the button below the answer.",
    "If we have the party's voting record, you can also check the answer against relevant legislative proposals.",
  ],

  labels: {
    processHeading: "Here's how it works:",
    originHeading: 'How did wahl.chat come about?',
    wahlOMatListLeadIn: 'With wahl.chat, you can:',
    sourcesLinkText: '/sources',
    plusButton: { phrase: 'plus button', iconSuffix: ' button' },
    pdfTitle: 'wahl.chat - Guide',
    pdfFileName: 'wahl-chat-guide.pdf',
  },

  accordionContent: [
    {
      id: 'questions',
      title: 'What questions can I ask?',
      content: {
        intro:
          "You can ask anything you'd like to know about the parties' positions. If you want to compare several parties, you can either add them to the chat or simply mention them in your question. You can also ask about general topics, such as how an election works.",
        sections: [
          {
            subtitle: 'Examples of party-specific questions:',
            list: PARTY_SPECIFIC_QUESTIONS,
          },
          {
            subtitle: 'Examples of comparative questions:',
            list: COMPARE_QUESTIONS,
          },
          {
            subtitle: 'Examples of general questions:',
            list: GENERAL_QUESTIONS,
          },
        ],
      },
    },
    {
      id: 'elections-supported',
      title: 'Which elections are supported?',
      content: {
        intro: 'We currently support the following elections:',
        list: [
          'Baden-Württemberg state election - 8 March 2026',
          'Rhineland-Palatinate state election - 22 March 2026',
          'Munich local election - 8 March 2026',
        ],
        outro:
          "In addition, the **federal level** area answers general questions about the parties' positions.",
      },
    },
    {
      id: 'number-parties',
      title: 'How many parties can I chat with?',
      content: {
        paragraphs: [
          `You can start a chat with up to ${MAX_SELECTABLE_PARTIES} parties at once, and you can still bring in other parties while you chat.`,
          'You can also easily add more parties to the chat, or remove them again, using the plus button above the text field.',
        ],
      },
    },
    {
      id: 'position',
      title: 'Put position into context',
      content: {
        paragraphs: [
          "When you click this button below one of the messages, the message's position is put into context. It considers the following criteria: feasibility, and short-term and long-term effects.",
          'For this we use up-to-date information and sources from the internet, provided to us by Perplexity.ai.',
        ],
      },
    },
    {
      id: 'voting-behavior-analyze',
      title: 'Analyse voting behaviour',
      content: {
        paragraphs: [
          'This feature lets you put a party\'s answer into the context of past votes in the Bundestag. You can also click "Show votes" to see and visualise detailed information on the relevant votes. This lets you measure the plans in a party\'s programme against how it actually behaves in politics.',
        ],
      },
    },
    {
      id: 'data',
      title: 'What data is used?',
      content: {
        intro:
          'To give well-founded, source-based answers, wahl.chat draws on a wide range of data sources:',
        orderedList: [
          "Party documents: Our data is based on party programmes, election manifestos, position papers and other documents published by the parties, to build a comprehensive picture of the parties' positions.",
          "Plenary records: We take what the parties actually said in parliament from the Bundestag's plenary records, published through the Documentation and Information System for Parliamentary Materials (DIP) at dip.bundestag.de.",
          'Voting behaviour in the Bundestag: To analyse voting behaviour, we use data on Bundestag votes provided by abgeordnetenwatch.de. This data makes it possible to compare party positions with how the parties actually vote.',
          'Web sources for putting positions into context: For a nuanced assessment of positions, wahl.chat uses the Perplexity.ai service, which draws on high-quality web sources such as news sites.',
        ],
        outro:
          'All the sources wahl.chat uses are listed on our website at /sources.',
      },
    },
    {
      id: 'guidelines',
      title: 'What guidelines does wahl.chat follow in its answers?',
      content: {
        intro: 'The following guidelines apply to the answers in the chats:',
        orderedList: [
          'Source-based: Answers should rest on the relevant statements in the programme excerpts provided.',
          'Neutrality: Party positions should be presented neutrally and without judgement.',
          'Transparency: Every statement should link directly to the relevant sources, so the content can be examined and checked in detail.',
        ],
      },
    },
    {
      id: 'party-selection',
      title: 'How are the parties selected?',
      content: {
        paragraphs: [
          'The original selection of parties for the federal context was made before the 2025 Bundestag election and was based on which parties had published election manifestos. We now want to offer as complete a selection of parties as possible for the other supported elections too, step by step, and would love your help with that.',
          "If a party is missing, feel free to email us its election manifesto, party programme or other relevant documents as a PDF at info@wahl.chat, and we'll add it as soon as we can.",
        ],
      },
    },
    {
      id: 'about-founders',
      title: 'Who is behind wahl.chat and how did it come about?',
      content: {
        intro:
          'wahl.chat was founded by five students from LMU, TUM and the University of Cambridge. They came together in Cambridge for a joint research project on AI and have since completed their studies.',
        sections: [
          {
            subtitle: 'The founding members and their current positions:',
            list: [
              'Sebastian Maier - PhD student at LMU Munich',
              'Anton Wyrowski - Developer at Perplexity',
              'Michel Schimpf - PhD student at the University of Cambridge',
              'Robin Frasch - PhD student at the University of Hamburg',
              'Roman Mayr - Developer at Knowunity',
            ],
          },
        ],
        origin:
          "At the end of November 2024, the team was having lunch together in Cambridge. The conversation turned to the fact that the grandfather of German rapper Ski Aggu had worked on the Wahl-O-Mat. The idea came up of building a new Wahl-O-Mat that uses AI to place your own opinions on the campaign issues. But wouldn't it be even more exciting to turn things around and have an in-depth chat with the parties that matter to you? Not just getting a verdict on predefined statements, but being able to raise your own individual concerns? And so, at the end of November 2024, the idea for wahl.chat was born.",
        outro: 'You can find more information at /about-us.',
      },
    },
    {
      id: 'wahl-o-mat-difference',
      title: 'How is wahl.chat different from the Wahl-O-Mat?',
      content: {
        intro:
          'With the Wahl-O-Mat, you respond to set statements with "agree", "neutral" or "disagree". wahl.chat, on the other hand, is like an open conversation that helps you better understand what the parties are calling for.',
        orderedList: [
          'Ask questions about the topics that interest you most.',
          "Go into detail to understand exactly what the parties' terms, ideas and plans mean.",
          'Critically assess positions to weigh up the pros and cons.',
        ],
      },
    },
    {
      id: 'data-privacy',
      title: 'Is my data safe when I use wahl.chat?',
      content: {
        paragraphs: [
          "Yes, wahl.chat works without cookies and without collecting personal data. Only the chats are stored, in anonymised form. Access controls prevent unauthorised access to other people's chats.",
          'Even so, you should avoid writing sensitive personal information in the chats.',
        ],
      },
    },
    {
      id: 'usage-statistics',
      title: 'Are usage statistics collected?',
      content: {
        paragraphs: [
          'To keep improving wahl.chat, website requests and anonymised chat histories are used to compile aggregate statistics, such as the number of questions answered or the parties people chat with most.',
          "As we accompany the development of wahl.chat with research, we will from time to time give our users the chance to take part in studies. Taking part will be 100% voluntary, and declining will not affect your use of wahl.chat in any way. In these studies we will use the anonymised usage statistics to analyse wahl.chat's effects and further increase its positive impact.",
        ],
      },
    },
    {
      id: 'learning',
      title: 'Does wahl.chat learn on its own over time?',
      content: {
        paragraphs: [
          'No, chat histories are not used to further train the LLMs. We are, however, continuously working to improve the quality of the answers, keep our data up to date and plan to add more relevant documents for generating answers.',
        ],
      },
    },
    {
      id: 'contribute',
      title: 'How can I contribute to wahl.chat?',
      content: {
        paragraphs: [
          'wahl.chat is an open-source project and our code is publicly available on GitHub at https://github.com/wahl-chat.',
          "We're always glad of support and are always looking for volunteers who want to help us strengthen democracy. If you'd like to get involved, get in touch at info@wahl.chat.",
        ],
      },
    },
  ],
};
