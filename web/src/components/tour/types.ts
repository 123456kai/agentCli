export type TourStep = {
  order: number;
  title: string;
  file: string;
  description: string;
  next_read?: {
    file: string;
    reason: string;
  };
  key_lines?: string;
};

export type TourData = {
  title: string;
  steps: TourStep[];
};
