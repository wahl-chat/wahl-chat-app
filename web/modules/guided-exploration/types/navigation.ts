/**
 * Navigation Types
 * Represents navigation state and breadcrumb
 */

export type BreadcrumbLevel = 'root' | 'branch' | 'leaf';

export interface BreadcrumbItem {
  /** Node identifier */
  id: string;
  /** Display name */
  name: string;
  /** Level in the hierarchy */
  level: BreadcrumbLevel;
}

export interface NavigationState {
  /** Current exploration identifier */
  explorationId: string;
  /** Current path in the tree: [] = root, ["housing"] = topic, ["housing", "rent-control"] = subtopic */
  currentPath: string[];
  /** Breadcrumb trail */
  breadcrumb: BreadcrumbItem[];
}

export interface SiblingNavigation {
  /** Previous sibling leaf */
  previous?: {
    id: string;
    name: string;
  };
  /** Next sibling leaf */
  next?: {
    id: string;
    name: string;
  };
}
