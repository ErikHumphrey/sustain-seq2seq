import requests, os, sys, json, string
import tarfile
import unicodedata

def process_tgz(tgz_file, dest_folder, size):

    tar = tarfile.open(tgz_file, 'r')
    files = tar.getnames()
    files = [x for x in files if x.endswith(".story")]
    print("Files in TAR file: "+str(len(files)))
    print()

    with open(dest_folder,"w",encoding="utf8") as wri:
        for i in range(len(files)):
            if i % 50 == 0:
                print("{} / {}\t({}) ...".format(i, len(files), i*100.0/float(len(files))))
        
            #f=tar.extractfile("./dailymail/stories/06588a8ab74f068ec61b89de9ca03a28f5ebd6f4.story")
            f=tar.extractfile(files[i])
            byte_content=f.readlines()

            # convert all byte arrays to strings
            content = [b.decode("utf-8").strip() for b in byte_content]            
            
            x,y = process_individual_file(content)
            for line in x+y:
                if line!="":
                    wri.write(line.strip()+"\n")       
            
            
def process_individual_file(content): # content is an array of raw uft-8 strings (all lines)
    # search for "UPDATED:"
    for i in range(len(content)):
        if content[i].startswith("UPDATED:"):
            content = content[i+4:]
            break
        if content[i].startswith("Last updated at"):
            content = content[i+2:]
            break

    # search for "--" in first line
    index = content[0].find("--")
    if index>0:
        content[0] = content[0][index+3:]    
    #print(">>>>>>>>>>>>>>>>>>>>>>>>")
    #print(content[0])
    
    #print("\n\n\n------")
    #print(content)

    
    # normal process
    i = 0
    state = 0
    x = []
    y = []
    
    
    line = content[0].replace(u'\xa0', u' ')
    line = line.replace(u'\u00a320M', u'-')                    
    line = unicodedata.normalize('NFKD', line)#.encode('ascii','ignore')
    
    x.append(line)
    for i in range(1, len(content)): 
        if content[i] == "":
            continue
        
        line = content[i].replace(u'\xa0', u' ')
        line = line.replace(u'\u00a320M', u'-')                
        #print()
        #print(line)
        line = unicodedata.normalize('NFKD', line)#.encode('ascii','ignore')
        #print(line)
        #input("")
        #\u00a320
        
        if line == "@highlight":
            state = 1 # switch to writing to y

        if state == 0:
            if content[i-1] == "": # add to new sentence
                x.append(line)
            else: # concat to last sentence
                x[-1] = x[-1] + " " + line
        else:
            if line == "@highlight" or line == "":
                continue                
            if content[i-1] == "": # add to new sentence
                y.append(line)
            else: # concat to last sentence
                y[-1] = y[-1] + " " + line

    # after processing
    y = [elem.replace("NEW: ","").replace("New :","").strip() for elem in y]
    
    for i in range(len(y)):
        if y[i][-1] not in string.punctuation:
            y[i] += "."
    
    #print()
    #print(x)
    #print(y)
            
    if len(y) == 0 or len(x) == 0:
        print(content)
        print("\n x and y below:")
        print(x)
        print(y)    
        input("ERROR")
        
    return x, y
    
    

tgz_file = "cnn_stories.tgz"   
process_tgz(tgz_file, os.path.join("text_only","cnn.txt"), 1000)

tgz_file = "dailymail_stories.tgz"   
process_tgz(tgz_file, os.path.join("text_only","dm.txt"), 1000)

