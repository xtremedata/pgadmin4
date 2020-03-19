//////////////////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////////////////

export function nodeHasProfiling(node, item) {
  if(typeof(node.hasProfiling) === 'function') {
    const treeHierarchy = node.getTreeNodeHierarchy(item);
    return node.hasProfiling(treeHierarchy);
  }
  return node.hasProfiling;
}
