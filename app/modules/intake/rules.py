from .reader import read_source
FIELDS=['id', 'ticket', 'kind', 'weight', 'unit', 'fish', 'price', 'rate', 'version', 'replaces', 'paid']
OPTIONAL=['boat', 'id_tail']
def apply(state):
    read_source(state,FIELDS,{'编号':'id'},optional=OPTIONAL)
