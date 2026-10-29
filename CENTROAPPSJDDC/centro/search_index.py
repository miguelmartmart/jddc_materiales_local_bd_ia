"""Busqueda en memoria con varios terminos y acentos;sin indice persistente."""
from . import knowledge


class SearchIndex:
    def __init__(self):self._cache={}

    def select(self,records,query):
        terms=knowledge.normalize(query).split()
        if not terms:
            self._cache={}
            return list(enumerate(records))
        active={};result=[]
        for index,record in enumerate(records):
            key=(record['name'],record['detail'],record['path'])
            cached=self._cache.get(key)
            if cached is None:cached=(' '.join(key).casefold(),None)
            folded,normalized=cached
            matched=all(term in folded for term in terms)
            if not matched and not folded.isascii():
                if normalized is None:normalized=knowledge.normalize(folded)
                matched=all(term in normalized for term in terms)
            active[key]=(folded,normalized)
            if matched:result.append((index,record))
        self._cache=active
        return result

    @property
    def cached_records(self):return len(self._cache)
