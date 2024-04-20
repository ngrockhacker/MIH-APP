values_in_list = int(input("How many values in the list : "))
list=[]
for a in range(values_in_list):
    print()
    val = int(input("ENter a value to add to the list : "))
    print()
    list.append(val)

print(list)

for i in range(1,len(list)):
    
    key=list[i]
    j=i-1
    while j>=0 and key<list[j]:
        list[j+1]=list[j]
        j=j-1
    else:
        list[j+1]=key
        
        
list.reverse()
print(list)