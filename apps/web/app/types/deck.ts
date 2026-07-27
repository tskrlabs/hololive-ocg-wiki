export type Deck = {
  // 1
  oshiCardIds: string[];

  // 50
  mainCardIds: string[];

  // 20
  yellCardIds: string[];

  id: string;
  name?: string;
  author?: string;
  version: string;
};

export type DeckCollection = Deck[];
