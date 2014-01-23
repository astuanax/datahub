package DataHubORM;

import java.lang.annotation.Annotation;
import java.lang.reflect.Field;
import java.lang.reflect.Type;
import java.sql.Date;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;


import datahub.DHCell;
import datahub.DHData;
import datahub.DHField;
import datahub.DHQueryResult;
import datahub.DHRow;
import datahub.DHSchema;
import datahub.DHTable;
import datahub.DHType;

import DataHubAnnotations.Association;
import DataHubAnnotations.Column;
import DataHubAnnotations.IntegerField;
import DataHubAnnotations.Table;
import DataHubAnnotations.Association.AssociationTypes;
import DataHubAnnotations.Column.Index;
import DataHubORM.QueryRefinementObject.OrderBy;
import DataHubResources.Resources;
import DataHubWorkers.DataHubWorker;
import DataHubWorkers.GenericCallback;
import DataHubWorkers.GenericExecutable;
import Examples.TestModel;

@Table(name="")
public class DataHubModel<T extends DataHubModel>{
	
	
	private static DataHubDatabase db;
	
	private HashMap<String,String> errors;
	
	@Column(name="id", index=Index.PrimaryKey)
	@IntegerField(Serial=true)
	public int id;
	
	public DataHubModel() throws DataHubException{
		if(db==null){
			throw new DataHubException("Database for model class must be set before any models can be created!");
		}
		this.id = 0;
		this.errors = new HashMap<String,String>();
		
		//set default values
		this.setDefaults();
		
		for(Field f: this.getClass().getFields()){
			if(DataHubConverter.isDataHubArrayListSubclass(f.getType()) && DataHubConverter.hasAssociation(f)){
				try{
					Association a = f.getAnnotation(Association.class);
					DataHubArrayList d = (DataHubArrayList) f.getType().newInstance();
					d.setCurrentModel(this);
					d.setAssociation(a);
					Resources.setField(this, f.getName(), d);
				}catch(Exception e){
					e.printStackTrace();
					throw new DataHubException("Could not set database for DataHubArrayList class!");
				}
			}
		}
	}
	public QueryRefinementObject getDefaultQueryRefinemnetObject(){
		return new QueryRefinementObject();
	}
	public void setDefaults(){
		
	}
	public synchronized boolean validate(){
		return true;
	}
	public synchronized void beforeSave(){
		
	}
	public synchronized void afterSave(){
		
	}
	public synchronized void beforeDestroy(){
		
	}
	public synchronized void afterDestroy(){
		
	}
	public static void setDatabase(DataHubDatabase database) throws DataHubException{
		//TODO: figure out why this is getting set more than once
		db=database;
		/*if(db == null){
			db = database;
		}else{
			throw new DataHubException("Database can only be set once for the Model Class!");
		}*/
	}
	public static DataHubDatabase getDatabase(){
		return db;
	}
	public void saveAsync(final GenericCallback<T> succeedCallback, final GenericCallback<DataHubException> failCallback) throws DataHubException{
		final T object = (T) this;
		DataHubException e;
		DataHubWorker<T> dhw = new DataHubWorker<T>(new GenericExecutable<T>(){

			@Override
			public T call() throws DataHubException{
				save();
				return object;
			}}, succeedCallback,failCallback, db.getDataHubWorkerMode());
		dhw.execute();
	}
	public void destroyAsync(final GenericCallback<Void> succeedCallback, final GenericCallback<DataHubException> failCallback) throws DataHubException{
		DataHubWorker<Void> dhw = new DataHubWorker<Void>(new GenericExecutable<Void>(){

			@Override
			public Void call() {
				destroy();
				return null;
			}}, succeedCallback, failCallback, db.getDataHubWorkerMode());
		dhw.execute();
	}
	public synchronized void save() throws DataHubException{
		//db.hitCount = 0;
		//db.missCount = 0;
		//System.out.println("before save");
		if(validate()){
			beforeSave();
			String query = this.save(DataHubDatabase.MAX_SAVE_RECURSION_DEPTH, new ConcurrentHashMap<String,Object>());
			getDatabase().query(query);
			updateModel(DataHubDatabase.MAX_LOAD_RECURSION_DEPTH,new ConcurrentHashMap<String,Object>(),new ConcurrentHashMap<String,Object>());
			afterSave();
		}else{
			DataHubException dhe = new DataHubException("Model failed validation and resulted in the following errors: "+ this.errors.toString());
			this.errors = new HashMap<String,String>();
			throw dhe;
		}
		//System.out.println("after save");
	}
	String save(int recursionDepthLimit,ConcurrentHashMap<String,Object> localCache){
		//System.out.println(modelsAlreadySaved);
		//System.out.println(this.getClass());
		if(recursionDepthLimit <= 0){
			//System.out.println("broke"+modelsAlreadySaved.contains(this.getClass()));
			return "";
		}
		ArrayList<String> queries = new ArrayList<String>();
		try{
			String query = "";
			//fix this
			if(!this.validId()){
				query = "INSERT INTO "+this.getCompleteTableName()+"("+this.getTableBasicFieldNames()+")"+" VALUES( "+getBasicFieldValues()+")";
			}else{
				query = "UPDATE "+this.getCompleteTableName()+" SET "+generateAssignmentSQLRep()+" WHERE "+"id="+this.id;
			}
			//System.out.println(query);
			//just make query no recursion
			//getDatabase().query(query);
			
			if(!this.validId()){
				getDatabase().query(query);
				//System.out.println(query);
				//get new id
				updateModelId(recursionDepthLimit);
			}else{
				queries.add(query);
			}
			
			//recursively save all fields
			for(Field f:this.getClass().getFields()){
				if(this.hasAssociation(f.getName())){
					Object o = f.get(this);
					if(o != null){
						if(DataHubConverter.isModelSubclass(f.getType())){
							DataHubModel m = (DataHubModel) o;
							//TODO: fix this
							Association a = f.getAnnotation(Association.class);
							if(a.associationType() == AssociationTypes.BelongsTo){
								//System.out.println("updating");
								String associateTableName = this.getCompleteTableName();
								String queryBelongsTo = "UPDATE "+associateTableName+" SET "+a.foreignKey()+"="+m.id+" WHERE id="+this.id;
								//getDatabase().query(queryBelongsTo);
								queries.add(queryBelongsTo);
							}
							if(a.associationType() == AssociationTypes.HasOne){
								String associateTableName = m.getCompleteTableName();
								String queryHasOne = "UPDATE "+associateTableName+" SET "+a.foreignKey()+"="+m.id+" WHERE id="+this.id;
								//getDatabase().query(queryHasOne);
								queries.add(queryHasOne);
							}
							//System.out.println(m);
							String otherQueries = m.save(recursionDepthLimit-1,localCache);
							queries.add(otherQueries);
						}
						//has many or HABTM relationship
						if(DataHubConverter.isDataHubArrayListSubclass(f.getType())){
							DataHubArrayList d = (DataHubArrayList) o;
							String otherQueries = d.save(recursionDepthLimit-1,localCache);
							queries.add(otherQueries);
						}
					}
				}
			}
			//updateModel(recursionDepthLimit,localCache);
		}catch(Exception e){
			e.printStackTrace();
		}
		return Resources.concatenate(queries, ";");
	}
	public synchronized void destroy(){
		try{
			beforeDestroy();
			String query = "DELETE FROM "+this.getCompleteTableName()+" WHERE "+"id="+this.id;
			//System.out.println(this.db.dbQuery("select * FROM "+this.db.getDatabaseName()+"."+this.getTableName()));
			//System.out.println(query);
			getDatabase().query(query);
			//System.out.println(getDatabase().query("SELECT * FROM "+this.getCompleteTableName()+" WHERE "+"id="+this.id, this.getClass()));
			//possibly garbage collect object
			//recursively save all fields
			afterSave();
			//TODO: supporty cascading delete, but doing it in table definition so that server does it
		}catch(Exception e){
			e.printStackTrace();
		}
	}
	public void allAsync(final GenericCallback<ArrayList<T>> succeedCallback, final GenericCallback<DataHubException> failCallback) throws DataHubException{
		DataHubWorker<ArrayList<T>> dhw = new DataHubWorker<ArrayList<T>>(new GenericExecutable<ArrayList<T>>(){

			@Override
			public ArrayList<T> call() {
				return all();
			}}, succeedCallback, failCallback, db.getDataHubWorkerMode());
		dhw.execute();
	}
	public void findAllAsync(final HashMap<String,Object> params, final GenericCallback<ArrayList<T>> succeedCallback, final GenericCallback<DataHubException> failCallback) throws DataHubException{
		findAllAsync(params, getDefaultQueryRefinemnetObject(),succeedCallback, failCallback);
	}
	public void findAllAsync(final HashMap<String,Object> params, final QueryRefinementObject qro, final GenericCallback<ArrayList<T>> succeedCallback, final GenericCallback<DataHubException> failCallback) throws DataHubException{
		DataHubWorker<ArrayList<T>> dhw = new DataHubWorker<ArrayList<T>>(new GenericExecutable<ArrayList<T>>(){

			@Override
			public ArrayList<T> call() {
				try {
					return findAll(params,qro);
				} catch (DataHubException e) {
					// TODO Auto-generated catch block
					e.printStackTrace();
					return null;
				}
			}}, succeedCallback, failCallback, db.getDataHubWorkerMode());
		dhw.execute();
	}
	public void findOneAsync(final HashMap<String,Object> params, final GenericCallback<T> succeedCallback, final GenericCallback<DataHubException> failCallback) throws DataHubException{
		findOneAsync(params,getDefaultQueryRefinemnetObject(), succeedCallback, failCallback);
	}
	public void findOneAsync(final HashMap<String,Object> params,final QueryRefinementObject qro, final GenericCallback<T> succeedCallback, final GenericCallback<DataHubException> failCallback) throws DataHubException{
		DataHubWorker<T> dhw = new DataHubWorker<T>(new GenericExecutable<T>(){

			@Override
			public T call() {
				try {
					return findOne(params, qro);
				} catch (DataHubException e) {
					// TODO Auto-generated catch block
					e.printStackTrace();
					return null;
				}
			}}, succeedCallback, failCallback, db.getDataHubWorkerMode());
		dhw.execute();
	}
	public ArrayList<T> all(){
		String query = "select * FROM "+this.getCompleteTableName();
		return (ArrayList<T>) getDatabase().query(query, this.getClass());
	}
	public boolean exists(HashMap<String,Object> params) throws DataHubException{
		return exists(params, getDefaultQueryRefinemnetObject());
	}
	public boolean exists(HashMap<String,Object> params, QueryRefinementObject qro) throws DataHubException{
		T results = findOne(params, qro);
		if(results != null){
			return true;
		}
		return false;
	}
	public ArrayList<T> findAll(HashMap<String,Object> params) throws DataHubException{
		return findAll(params, getDefaultQueryRefinemnetObject());
	}
	public ArrayList<T> findAll(HashMap<String,Object> params, QueryRefinementObject qro) throws DataHubException{
		System.out.println("new query");
		long start = System.currentTimeMillis();
		if(params.size() == 0){
			return new ArrayList<T>();
		}
		//TODO: querying by related object
		//Ideas: 1) if we get a model object then see if there is an association between that object's class
		//and this class 2) if so use the association type to do the appropriate queries 3) if not throw an
		//invalid query exception because it does not make sense to query a model using a related object
		//if there is no association
		//String query = "select * FROM "+this.getCompleteTableName()+" WHERE "+ queryToSQL(params);
		String query = modelQueryToSQL(params,qro);
		ArrayList<T> results = (ArrayList<T>) getDatabase().query(query, this.getClass());
		System.out.println("query took:"+(System.currentTimeMillis()-start));
		return results;
	}
	public T findOne(HashMap<String,Object> params) throws DataHubException{
		QueryRefinementObject qro = getDefaultQueryRefinemnetObject();
		return findOne(params, qro);
	}
	public T findOne(HashMap<String,Object> params,QueryRefinementObject qro) throws DataHubException{
		System.out.println("new query");
		long start = System.currentTimeMillis();
		//TODO: querying by related object
		if(params.size() != 0){
			qro.setQueryLimitSize(1);
			String query = modelQueryToSQL(params,qro);
			ArrayList<T> data = (ArrayList<T>) getDatabase().query(query,this.getClass());
			System.out.println("query took:"+(System.currentTimeMillis()-start));
			//System.out.println(data);
			if(data.size() > 0){
				return (T) data.get(0);
			}
		}
		return null; 
	}
	public synchronized void findOnePoll(int interval, HashMap<String,Object> params, final GenericCallback<T> callback) throws DataHubException{
		throw new DataHubException("Not implemented yet!");
		
	}
	public synchronized void findAllPoll(int interval, HashMap<String,Object> params, final GenericCallback<T> callback) throws DataHubException{
		throw new DataHubException("Not implemented yet!");
	}
	//Keywords supported: CONTAINS, IN, BETWEEN, STARTS_WITH, ENDS_WITH 
	//BETWEEN - applies to DateTime, Double, Integer, strings
	//IN - list of values that column could be
	String modelQueryToSQL(HashMap<String,Object> query, QueryRefinementObject qro) throws DataHubException{
		class ModifierHandler{
			public String modifierToSQL(String modifier, Object val, Field f) throws DataHubException{
				ArrayList<String> symbols = new ArrayList<String>(Arrays.asList(new String[]{"<",">","<=",">="}));
				String out = "";
				String newMod = modifier.toLowerCase();
				if(newMod.equals("contains")){
					if(f.getType()==String.class && val.getClass()==String.class){
						String newVal = Resources.objectToSQL(val);
						out = "LIKE %"+newVal+"%";
					}
				}
				else if(newMod.equals("starts_with")){
					if(f.getType()==String.class && val.getClass()==String.class){
						String newVal = Resources.objectToSQL(val);
						out = "LIKE "+newVal+"%";
					}
				}
				else if(newMod.equals("ends_with")){
					if(f.getType()==String.class && val.getClass()==String.class){
						String newVal = Resources.objectToSQL(val);
						out = "LIKE %"+newVal;
					}
				}
				//TODO: may need to check if type of object in arraylist matches the type of the field
				else if(newMod.equals("in")){
					if(val.getClass() == ArrayList.class){
						ArrayList<Object> list = (ArrayList<Object>) val;
						if(list.size()>0){
							out = "in ("+Resources.converToSQLAndConcatenate(list,",")+")";
						}
					}
				}
				else if(newMod.equals("between")){
					if(Resources.isNumeric(f.getType()) || f.getType() == Date.class || f.getType() == String.class){
						if(val.getClass() == ArrayList.class){
							ArrayList<Object> list = (ArrayList<Object>) val;
							if(list.size() == 2){
								out = "between "+Resources.converToSQLAndConcatenate(list,"AND");
							}
						}
					}
				}
				else if(symbols.contains(newMod)){
					out = newMod+Resources.objectToSQL(val);
				}else{
					//do pure equals
					out = "="+Resources.objectToSQL(val);
				}
				return out;
			}
		}
		ArrayList<String> keyVal = new ArrayList<String>();
		String tables = this.getCompleteTableName();
		for(String field:query.keySet()){
			//require a query hashmap to look like id >: 5, age <:10
			String[] fieldParams = field.split(" ");
			String fieldName = fieldParams[0];
			String fieldModifier = "";
			if(fieldParams.length > 1){
				fieldModifier = fieldParams[1];
			}
			if(hasFieldAndColumnBasic(fieldName)){//also check if has column annotation
				Field f = Resources.getField(this.getClass(), fieldName);
				
				//need to get the actual column name before query can be made
				Column c = f.getAnnotation(Column.class);
				
				Object val = query.get(fieldName);
				
				String newVal = new ModifierHandler().modifierToSQL(fieldModifier, val, f);
			
				keyVal.add(this.getCompleteTableName()+"."+c.name()+newVal);
				continue;
			}
			
			//if there is a model object in the hashmap, then only support equals to
			Object o = query.get(fieldName);
			HashMap<Field,DHType> fields = DataHubConverter.extractAssociationsFromClass(this.getClass()).get(this.getClass());
			Field match = null;
			for(Field f: fields.keySet()){
				if(DataHubConverter.isModelSubclass(f.getType())){
					if(f.getType() == o.getClass()){
						match = f;
					}
				}
				//add part of query that searches for all records that have the desired object in their list of objects of that type
				//i.e. a model has many users and you want to find all instances of the model that have the specified user in their lists
				//when querying by object and the member type is a DataHubArrayList then provide a normal arraylist with a list
				//of objects that would go into the DataHubArrayList for which you want to find a record whose DataHubArrayList
				//contains those elements
				if(DataHubConverter.isDataHubArrayListSubclass(f.getType())){
					
				}
			}
			if(match!=null){
				Association a = match.getAnnotation(Association.class);
				DataHubModel m;
				if(DataHubConverter.isModelSubclass(o.getClass())){
					m = (DataHubModel) o;
				}else{
					//TODO:fix this
					throw new DataHubException("Association found but query object is not a model class!");
				}
				String newKey = "";
				//System.out.println(a.associationType());
				switch(a.associationType()){
					case HasOne:
						newKey = this.getCompleteTableName()+".id in(select "+a.foreignKey()+" from "+m.getCompleteTableName()+
						" where "+m.getCompleteTableName()+".id="+m.id+")";
						//System.out.println(newKey);
						break;
					case BelongsTo:
						newKey = this.getCompleteTableName()+".id in(select "+this.getCompleteTableName()+".id from "+this.getCompleteTableName()+
						" where "+this.getCompleteTableName()+"."+a.foreignKey()+"="+m.id+")";
						break;
					/*
					case HasMany:
						break;
					case HasAndBelongsToMany:
						String linkTableSelectKey;
						String linkTableSearchKey;
						if(a.leftTableForeignKey().equals(a.foreignKey())){
							linkTableSelectKey = a.rightTableForeignKey();
							linkTableSearchKey = a.leftTableForeignKey();
						}else if(a.rightTableForeignKey().equals(a.foreignKey())){
							linkTableSelectKey = a.leftTableForeignKey();
							linkTableSearchKey = a.rightTableForeignKey();
						}else{
							throw new DataHubException("For HABTM association, the foreign key must match either the left or the right key in the linking table!");
						}
						String query1 = "select ("+linkTableSelectKey+") from "+db.getDatabaseName()+"."+a.linkingTable()+" where "+linkTableSearchKey+"="+this.id;
						//TODO:fix this
						newKey = this.getCompleteTableName()+".id in("+query1+")";
						break;*/
					default:
						//throw exception
						break;
				}
				keyVal.add(newKey);
			}else{
				throw new DataHubException("No association found in model being queried for "+o.getClass()+"! Cannot perform query!");
			}
		}
		//check to see if tables is not null and whereclause is not null
		String whereClause = Resources.concatenate(keyVal,"AND");
		//String queryStr = "select * from "+tables+" where "+Resources.concatenate(keyVal,"AND")
		String queryStr = "";
		if(qro.getDistinctFieldNames() != null){
			for(String fieldName:qro.getDistinctFieldNames()){
				if(Resources.hasField(this.getClass(), fieldName)){
					throw new DataHubException("Invalid field in Distinct Field Names!");
				}
			}
			String distinctFieldNames = Resources.concatenate(Arrays.asList(qro.getDistinctFieldNames()), ",");
			queryStr+="select distinct "+distinctFieldNames+" from "+tables+" where "+whereClause;
		}else{
			queryStr+="select * from "+tables+" where "+whereClause;
		}
		if(qro.getGroupByFields() != null){
			String[] groupByFields = qro.getGroupByFields();
			for(String groupByField: groupByFields){
				if(!Resources.hasField(this.getClass(), groupByField)){
					throw new DataHubException("Invalid field in Group By Field Name!");
				}
			}
			queryStr+=" group by "+Resources.concatenate(Arrays.asList(groupByFields), ",");
		}
		if(qro.getOrderByFields() != null){
			OrderBy[] orderByFields = qro.getOrderByFields();
			ArrayList<String> orderByComponents = new ArrayList<String>();
			for(OrderBy orderByField: orderByFields){
				if(!Resources.hasField(this.getClass(), orderByField.getOrderByField())){
					throw new DataHubException("Invalid field in Group By Field Name!");
				}
				String orderByComponent = orderByField.getOrderByField()+" ";
				switch(orderByField.getOrderByType()){
					case Ascending:
						orderByComponent+="asc";
						break;
					case Descending:
						orderByComponent+="desc";
						break;
					default:
						throw new DataHubException("Invalid OrderByType!");
				}
				orderByComponents.add(orderByComponent);
			}
			queryStr+=" order by "+Resources.concatenate(orderByComponents, ",")+" ";

		}
		if(qro.getQuerySizeLimit()!=0){
			queryStr+=" limit "+qro.getQuerySizeLimit();
		}
		//System.out.println(queryStr);
		return queryStr;
	}
	boolean hasFieldAndColumnBasic(String name){
		boolean out = false;
		try{
			Field f = this.getClass().getField(name);
			if(DataHubConverter.hasColumnBasic(f)){
				out= true;
			}
		}catch(Exception e){
			
		}
		return out;
	}
	boolean hasAssociation(String name){
		boolean out = false;
		try{
			Field f = this.getClass().getField(name);
			if(DataHubConverter.hasAssociation(f)){
				out= true;
			}
		}catch(Exception e){
			
		}
		return out;
	}
	
	
	String generateAssignmentSQLRep(){
		return generateSQLRep(",", false);
	}
	String generateQuerySQLRep(){
		return generateSQLRep("AND", true);
	}
	String generateSQLRep(String linkSymbol, boolean query){
		HashMap<Class,HashMap<Field,DHType>> models = DataHubConverter.extractColumnBasicFromClass(this.getClass());
		HashMap<Field,DHType> currentModel = models.get(this.getClass());
		ArrayList<String> fieldData = new ArrayList<String>();
		for(Field f:currentModel.keySet()){
			//System.out.println(f.getName());
			Column c = f.getAnnotation(Column.class);
			if(c.name().equals("id") && !this.validId()){
				continue;
			}
			try{
				Object o = f.get(this);
				String entry = c.name()+Resources.objectToSQLModifier(o, query)+Resources.objectToSQL(o);
				fieldData.add(entry);
			}catch(Exception e){
				e.printStackTrace();
			}
		}
		return Resources.concatenate(fieldData,linkSymbol);
	}
	String getTableBasicFieldNames(){
		HashMap<Class,HashMap<Field,DHType>> models = DataHubConverter.extractColumnBasicFromClass(this.getClass());
		HashMap<Field,DHType> currentModel = models.get(this.getClass());
		ArrayList<String> getFieldTableNames = new ArrayList<String>();
		for(Field f: currentModel.keySet()){
			//System.out.println(f.getName());
			Column c = f.getAnnotation(Column.class);
			if(c.name().equals("id")){
				continue;
			}
			getFieldTableNames.add(c.name());
		}
		return Resources.concatenate(getFieldTableNames,",");
	}
	String getBasicFieldValues(){
		HashMap<Class,HashMap<Field,DHType>> models = DataHubConverter.extractColumnBasicFromClass(this.getClass());
		HashMap<Field,DHType> currentModel = models.get(this.getClass());
		//System.out.println(this.getTableName());
		//System.out.println(currentModel);
		ArrayList<String> fieldData = new ArrayList<String>();
		for(Field f: currentModel.keySet()){
			Column c = f.getAnnotation(Column.class);
			if(c.name().equals("id")){
				continue;
			}
			String value = Resources.getFieldSQLStringRep(this, f.getName());
			//System.out.println(value);
			fieldData.add(value);
		}
		return Resources.concatenate(fieldData,",");
	}
	public void refreshModel(){
		updateModel(DataHubDatabase.MAX_LOAD_RECURSION_DEPTH,new ConcurrentHashMap<String,Object>(),new ConcurrentHashMap<String,Object>());
	}
	public void refreshField(String fieldName) throws DataHubException{
		getDatabase().updateModelObjectField(fieldName, this,DataHubDatabase.MAX_LOAD_RECURSION_DEPTH,new ConcurrentHashMap<String,Object>(),new ConcurrentHashMap<String,Object>());
	}
	private void updateModel(int recursionDepthLimit, ConcurrentHashMap<String,Object> localCache,ConcurrentHashMap<String,Object> objectHash){
		getDatabase().updateModelObject(this,recursionDepthLimit,localCache,objectHash);
	}
	private void updateModelId(int recursionDepthLimit){
		getDatabase().updateModelId(this);
	}
	private T newInstance() throws InstantiationException, IllegalAccessException{
		return (T) getClass().newInstance();
	}
	public String getTableName(){
		Table t = this.getClass().getAnnotation(Table.class);
		if(t != null){
			return t.name();
		}
		return null;
	}
	public String getCompleteTableName(){
		return getDatabase().getDatabaseName()+"."+this.getTableName();
	}
	
	//required for arraylist to work
	@Override
	public boolean equals(Object o){
		if(DataHubConverter.isModelSubclass(o.getClass())){
			DataHubModel other = (DataHubModel) o;
			String otherSQLRep = other.getCompleteTableName()+other.generateQuerySQLRep();
			String thisSQLRep = this.getCompleteTableName()+this.generateQuerySQLRep();
			//System.out.println(otherSQLRep);
			//System.out.println(thisSQLRep);
			if(thisSQLRep.equals(otherSQLRep)){
				return true;
			}
		}
		return false;
	}
	String generateNullSelect(){
		String query = "select ";
		HashMap<Class,HashMap<Field,DHType>> models = DataHubConverter.extractColumnBasicFromClass(this.getClass());
		HashMap<Field,DHType> currentModel = models.get(this.getClass());
		ArrayList<String> nulls = new ArrayList<String>();
		for(Field f: currentModel.keySet()){
			nulls.add("null");
		}
		HashMap<Class,HashMap<Field,DHType>> models1 = DataHubConverter.extractAssociationsFromClass(this.getClass());
		HashMap<Field,DHType> currentModel1 = models1.get(this.getClass());
		for(Field f1: currentModel1.keySet()){
			Association a = f1.getAnnotation(Association.class);
			if(a!=null && a.associationType() == AssociationTypes.BelongsTo){
				nulls.add("null");
			}
		}
		return query+Resources.concatenate(nulls,",");
	}
	@Override
	public String toString(){
		return this.getCompleteTableName()+this.generateQuerySQLRep();
	}
	public boolean validId(){
		if(this.id <= 0){
			return false;
		}
		return true;
	}
}
