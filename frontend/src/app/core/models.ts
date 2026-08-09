import type { components } from './api/schema';

export type Source = components['schemas']['Source'];
export type SourceDocument = components['schemas']['Document'];
export type IndexedChunk = components['schemas']['Chunk'];
export type Conversation = components['schemas']['Conversation'];
export type Message = components['schemas']['Message'];
export type Citation = components['schemas']['Citation'];
export type SourceType = components['schemas']['TypeEnum'];
export type SourceStatus = components['schemas']['StatusEnum'];
export type SystemStatus = components['schemas']['SystemStatus'];
export type DirectoryListing = components['schemas']['DirectoryListing'];
export type DirectoryEntry = components['schemas']['DirectoryEntry'];
export type DashboardMetrics = components['schemas']['DashboardMetrics'];
export type DailyQueryCount = components['schemas']['DailyQueryCount'];
export type Feedback = components['schemas']['Feedback'];
export type FeedbackRating = components['schemas']['FeedbackRatingEnum'];
// The read-only `feedback` nested in a Message — a separate schema
// object from `Feedback` (the POST/response shape) only because
// MessageSerializer.get_feedback() can't reuse analytics.serializers
// without rag depending on analytics. Same fields, different name.
export type MessageFeedback = components['schemas']['MessageFeedback'];
